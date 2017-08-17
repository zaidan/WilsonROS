#!/usr/bin/env python2

import roslib
import rospy
import smach
import smach_ros

import collections

from time import sleep
from random import getrandbits

from pprint import pprint

from actionlib.simple_action_client import SimpleActionClient, GoalStatus
from geometry_msgs.msg import Pose
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal

class WaitForZone(smach.State):
    def __init__(self, zones):
        smach.State.__init__(self, outcomes=['waiting_for_zone','got_zone'])
        self.zones = zones

    def execute(self, userdata):
        rospy.loginfo('Executing state WaitForZone')
        if len(self.zones) > 0:
            pprint(self.zones);
            return 'got_zone'
        else:
            # TODO: Load current zones
            self.zones.append(collections.deque([Pose(), Pose(), Pose(), Pose(), Pose()]))
            self.zones.append(collections.deque([Pose(), Pose(), Pose(), Pose(), Pose()]))
            self.zones.append(collections.deque([Pose(), Pose(), Pose(), Pose(), Pose()]))
            rospy.loginfo('update Data');
            return 'waiting_for_zone'

class GotZone(smach.State):
    def __init__(self, zones):
        smach.State.__init__(self, outcomes=['zone_empty','got_waypoint'])
        self.zones = zones

    def execute(self, userdata):
        rospy.loginfo('Executing state GotZone')
        if len(self.zones[0]) > 0:
            return 'got_waypoint'
        else:
            rospy.loginfo('zone empty, proceed with next zone')
            self.zones.popleft();
            pprint(self.zones);
            return 'zone_empty'

class GotWaypoint(smach.State):
    def __init__(self, zones, client):
        smach.State.__init__(self, outcomes=['move_to_waypoint', 'at_waypoint'])
        self.zones = zones
        self.client = client

    def execute(self, userdata):
        rospy.loginfo('Executing state GotWaypoint')
        if self.client.get_state() == GoalStatus.SUCCEEDED:
            # Remove waypoint
            self.zones[0].popleft()
            pprint(self.zones);
            return 'at_waypoint'
        else:
            rospy.loginfo('not at current waypoint, send move command and wait')
            # Send move command
            goal = MoveBaseGoal()
            pose = self.zones[0][0]
            goal.target_pose.pose = pose
            goal.target_pose.header.frame_id = 'map'
            goal.target_pose.header.stamp = rospy.Time.now()
            rospy.loginfo("Move to: " + str(pose))
            self.client.send_goal(goal)
            sleep(1)
            return 'move_to_waypoint'

class Planer:
    zones = collections.deque([])

    def __init__(self):
        rospy.init_node('wilson_ros_planer')

        self.client = SimpleActionClient('move_base', MoveBaseAction)
        
        rospy.loginfo("Waiting 5s for move_base action server...")
        self.client.wait_for_server(rospy.Duration(5))

        rospy.loginfo("Connected to move base server")

        # Create a SMACH state machine
        sm = smach.StateMachine(outcomes=['failed', 'stoped'])

        # Open the container
        with sm:
            # Add states to the container
            smach.StateMachine.add('WaitForZone', WaitForZone(self.zones), 
                                   transitions={'got_zone':'GotZone', 
                                                'waiting_for_zone':'WaitForZone'})

            smach.StateMachine.add('GotZone', GotZone(self.zones), 
                                   transitions={'zone_empty':'WaitForZone', 
                                                'got_waypoint':'GotWaypoint'})

            smach.StateMachine.add('GotWaypoint', GotWaypoint(self.zones, self.client), 
                                   transitions={'move_to_waypoint':'GotWaypoint', 
                                                'at_waypoint':'GotZone'})

        # Start Introspection Server
        sis = smach_ros.IntrospectionServer('sis', sm, '/SM_ROOT')
        sis.start()

        # Execute SMACH plan
        outcome = sm.execute()

        # Wait for ctrl-c to stop the application
        rospy.spin()
        sis.stop()
        
# main
def main():
    Planer();

if __name__ == '__main__':
    main()