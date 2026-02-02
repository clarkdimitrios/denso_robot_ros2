# Copyright (c) 2021 DENSO WAVE INCORPORATED
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: DENSO WAVE INCORPORATED

import os
import yaml
from ament_index_python.packages import get_package_share_directory, get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, TimerAction, SetEnvironmentVariable
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.actions import ExecuteProcess, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from typing import Text
from launch.launch_context import LaunchContext
from launch.substitution import Substitution
from typing import Iterable
from typing import Text
from launch.some_substitutions_type import SomeSubstitutionsType
from launch_ros.parameter_descriptions import ParameterValue

""" Function for loading a yaml file. """
def load_yaml(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path) as file:
            return yaml.safe_load(file)
    except OSError:  # parent of IOError, OSError *and* WindowsError where available
        return None


""" Substitution class for appending LaunchConfig parameters to a string.

Helpful for namespaces and/or MULTI-ROBOT applications.
"""
class TextJoinSubstitution(Substitution):
    """Substitution that join paths, in a platform independent way."""

    def __init__(
            self, substitutions: Iterable[SomeSubstitutionsType], text: Text,
            sequence: Text) -> None:
        super().__init__()
        """Create a TextJoinSubstitution."""
        from launch.utilities import normalize_to_list_of_substitutions
        self.__substitutions = normalize_to_list_of_substitutions(substitutions)
        self.__text = text
        self.__sequence = sequence

    @property
    def substitutions(self) -> Iterable[Substitution]:
        """Getter for variable_name."""
        return self.__substitutions

    def text(self) -> Text:
        """Getter for text."""
        return self.__text

    def describe(self) -> Text:
        """Return a description of this substitution as a string."""
        return "LocalVar('{}')".format(' + '.join([s.describe() for s in self.substitutions]))

    def perform(self, context: LaunchContext) -> Text:
        """Perform the substitution by retrieving the local variable."""
        performed_substitutions = [sub.perform(context) for sub in self.__substitutions]
        return self.__sequence.join(performed_substitutions) + self.__sequence + self.__text


""" Launch Description generator function. """
def generate_launch_description():

    declared_arguments = []

    # ----------------------- Denso specific arguments -----------------------
    declared_arguments.append(
        DeclareLaunchArgument(
            'model',
            description='Type/series of used denso robot.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'send_format', default_value='288',
            description='Data format for sending commands to the robot.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'recv_format', default_value='292',
            description='Data format for receiving robot status.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'bcap_slave_control_cycle_msec', default_value='8.0',
            description='Control frequency.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'ip_address', default_value='192.168.0.1',
            description='IP address by which the robot can be reached.'))
    # For Dual Arm
    declared_arguments.append(
        DeclareLaunchArgument(
            'right_ip_address', default_value='192.168.17.20',
            description='IP address by which the right robot can be reached.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'left_ip_address', default_value='192.168.17.21',
            description='IP address by which the left robot can be reached.'))
    
    declared_arguments.append(
        DeclareLaunchArgument(
            'slave_delay_ms', default_value='400',
            description='One-time delay (ms) before first slvMove on hardware'
        )
    )
    

    # ----------------------- Configuration arguments -----------------------
    declared_arguments.append(
        DeclareLaunchArgument(
            'description_package', default_value='denso_robot_descriptions',
            description='Description package with robot URDF/XACRO files.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'description_file', default_value='denso_robot.urdf.xacro',
            description='URDF/XACRO description file with the robot.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'moveit_config_package', default_value='denso_robot_moveit_config',
            description='MoveIt config package with robot SRDF/XACRO files.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'moveit_config_file', default_value='denso_robot.srdf.xacro',
            description='MoveIt SRDF/XACRO description file with the robot.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'namespace', default_value='',
            description="Prefix of the joint names, useful for multi-robot setup."))
    declared_arguments.append(
        DeclareLaunchArgument(
            'controllers_file', default_value='denso_robot_controllers.yaml',
            description='YAML file with the controllers configuration.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'moveit_controllers_file',
            default_value='moveit_controllers.yaml',
            description='MoveIt controllers config file.'))

    # ----------------------- EDITED: Multiple controllers supported -----------------------
    declared_arguments.append(
        DeclareLaunchArgument(
            'robot_controller', default_value='denso_joint_trajectory_controller',
            description='Robot controller(s) to start. Multiple controllers can be space or comma separated.'))
    
    # for HW
    declared_arguments.append(
        DeclareLaunchArgument(
            'launch_moveit',
            default_value='true',
            description='Start move_group and related MoveIt nodes.'
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            'launch_hw',
            default_value='true',
            description='Launch ros2_control_node and controllers (hardware).'
        )
    )

    # ----------------------- Execution arguments -----------------------
    declared_arguments.append(
        DeclareLaunchArgument('launch_rviz', default_value='true', description='Launch RViz?')
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            'sim', default_value='true',
            description='Start robot with fake hardware mirroring command to its states.'))
    declared_arguments.append(
        DeclareLaunchArgument(
            'verbose', default_value='false',
            description='Print out additional debug information.'))

    # ----------------------- Initialize Arguments -----------------------
    denso_robot_model = LaunchConfiguration('model')
    ip_address = LaunchConfiguration('ip_address')
    left_ip_address = LaunchConfiguration('left_ip_address')
    right_ip_address = LaunchConfiguration('right_ip_address')
    send_format = LaunchConfiguration('send_format')
    recv_format = LaunchConfiguration('recv_format')
    bcap_slave_control_cycle_msec = LaunchConfiguration('bcap_slave_control_cycle_msec')
    description_package = LaunchConfiguration('description_package')
    description_file = LaunchConfiguration('description_file')
    moveit_config_package = LaunchConfiguration('moveit_config_package')
    moveit_config_file = LaunchConfiguration('moveit_config_file')
    namespace = LaunchConfiguration('namespace')
    launch_rviz = LaunchConfiguration('launch_rviz')
    sim = LaunchConfiguration('sim')
    verbose = LaunchConfiguration('verbose')
    controllers_file = LaunchConfiguration('controllers_file')
    launch_moveit = LaunchConfiguration('launch_moveit')
    robot_controller = LaunchConfiguration('robot_controller')
    launch_hw = LaunchConfiguration('launch_hw')


    delay_env = SetEnvironmentVariable(
        name='DENSO_SLAVE_MODE_DELAY_MS',
        value=LaunchConfiguration('slave_delay_ms'),
        condition=IfCondition(
            PythonExpression([
                "'", sim, "' == 'false' and '", launch_hw, "' == 'true'"
            ])
        ),
    )   


    # ----------------------- Robot description -----------------------
    denso_robot_core_pkg = get_package_share_directory('denso_robot_core')

    denso_robot_control_parameters = {
        'denso_bcap_slave_control_cycle_msec': bcap_slave_control_cycle_msec,
        'denso_config_file': PathJoinSubstitution([denso_robot_core_pkg, 'config', 'config.xml'])}

    # Generate robot_description parameter by processing xacro file
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name='xacro')]), ' ',
            PathJoinSubstitution(
                [FindPackageShare(description_package), 'urdf', description_file]),
            ' ',
            'ip_address:=', ip_address, ' ',
            'left_ip_address:=', left_ip_address, ' ',
            'right_ip_address:=', right_ip_address, ' ',
            'model:=', denso_robot_model, ' ',
            'send_format:=', send_format, ' ',
            'recv_format:=', recv_format, ' ',
            'namespace:=', namespace, ' ',
            'verbose:=', verbose, ' ',
            'sim:=', sim, ' '
        ])
    robot_description = {'robot_description': ParameterValue(
        robot_description_content, value_type=str)}

    # ----------------------- MoveIt configuration -----------------------
    robot_description_semantic_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name='xacro')]), ' ',
            PathJoinSubstitution(
                [FindPackageShare(moveit_config_package), 'srdf', moveit_config_file]),
            ' ',
            'model:=', denso_robot_model, ' ',
            'namespace:=', namespace, ' '
        ])
    robot_description_semantic = {'robot_description_semantic': robot_description_semantic_content}
    kinematics_yaml = load_yaml('denso_robot_moveit_config', 'config/kinematics.yaml')
    robot_description_kinematics = {'robot_description_kinematics': kinematics_yaml}

    # OMPL Planning config
    ompl_planning_pipeline_config = {
        'move_group': {
            'planning_plugin': 'ompl_interface/OMPLPlanner',
            'request_adapters': 'default_planner_request_adapters/AddTimeOptimalParameterization' \
                + ' default_planner_request_adapters/FixWorkspaceBounds' \
                + ' default_planner_request_adapters/FixStartStateBounds' \
                + ' default_planner_request_adapters/FixStartStateCollision' \
                + ' default_planner_request_adapters/FixStartStatePathConstraints',
            'start_state_max_bounds_error': 0.1,
        }
    }
    ompl_planning_yaml = load_yaml('denso_robot_moveit_config', 'config/ompl_planning.yaml')
    ompl_planning_pipeline_config['move_group'].update(ompl_planning_yaml)

    # MoveIt controllers
    moveit_controllers = {
        'moveit_controller_manager': 'moveit_simple_controller_manager/MoveItSimpleControllerManager',
    }
    moveit_controllers_file = PathJoinSubstitution(
        [
            FindPackageShare(moveit_config_package), 'robots',
            denso_robot_model, 'config', LaunchConfiguration('moveit_controllers_file')
        ])

    # Trajectory execution settings
    trajectory_execution = {
        'moveit_manage_controllers': False,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.1,
    }

    # Planning scene monitor settings
    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
        'planning_scene_monitor_options': {
            'name': 'planning_scene_monitor',
            'robot_description': 'robot_description',
            'joint_state_topic': '/joint_states',
            'attached_collision_object_topic': '/move_group/planning_scene_monitor',
            'publish_planning_scene_topic': '/move_group/publish_planning_scene',
            'monitored_planning_scene_topic': '/move_group/monitored_planning_scene',
            'wait_for_initial_state_timeout': 100.0,
        },
    }

    # Occupancy map settings
    occupancy_map_monitor_parameters = {
        'sensors': ['3D_sensor'],
        '3D_sensor': {
            'sensor_plugin': '',
        },
    }

    # Joint limits
    robot_limits_file = PathJoinSubstitution(
        [
            FindPackageShare(moveit_config_package), 'robots',
            denso_robot_model, 'config/joint_limits.yaml'
        ])

    # Move group node
    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        # namespace=PythonExpression([
        #     '"', namespace, '".rstrip("_")'
        # ]),
        condition=IfCondition(launch_moveit),
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            robot_description_kinematics,
            robot_limits_file,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            moveit_controllers_file,
            occupancy_map_monitor_parameters,
            planning_scene_monitor_parameters,
            {'use_sim_time': sim}
        ])

    # Robot control node
    robot_controllers = PathJoinSubstitution(
        [
            FindPackageShare(moveit_config_package), 'robots',
            denso_robot_model, 'config', controllers_file
        ])
    # ----------------------- Namespaced control node -----------------------
    # When namespace is set (multi-robot), give the controller_manager a unique
    # node name so that two instances can coexist (e.g. right_controller_manager
    # and left_controller_manager).  The YAML's "controller_manager:" section
    # won't match the renamed node, so we load CM params as a dict instead.
    def _create_control_node(context, *args, **kwargs):
        ns_raw = LaunchConfiguration('namespace').perform(context)
        cm_name = (
            f'{ns_raw}controller_manager' if ns_raw else 'controller_manager'
        )

        model_val = LaunchConfiguration('model').perform(context)
        ctrl_file_val = LaunchConfiguration('controllers_file').perform(context)
        yaml_path = os.path.join(
            get_package_share_directory('denso_robot_moveit_config'),
            'robots', model_val, 'config', ctrl_file_val,
        )
        with open(yaml_path) as f:
            full_yaml = yaml.safe_load(f)

        cm_params = (
            full_yaml
            .get('controller_manager', {})
            .get('ros__parameters', {})
        )

        # Merge controller-specific params (joints, command_interfaces, …)
        # from the top-level YAML sections into cm_params as nested dicts.
        # This ensures the CM node receives them as proper hierarchical
        # parameters (e.g. right_arm_controller.joints) even when the CM
        # node name differs from 'controller_manager' (multi-robot case).
        for key, value in full_yaml.items():
            if key == 'controller_manager':
                continue
            if isinstance(value, dict) and 'ros__parameters' in value:
                if key not in cm_params:
                    cm_params[key] = {}
                if isinstance(cm_params[key], dict):
                    cm_params[key].update(value['ros__parameters'])
                else:
                    cm_params[key] = value['ros__parameters']

        return [
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                name=cm_name,
                parameters=[
                    robot_description,
                    cm_params,
                    denso_robot_control_parameters,
                ],
                output={'stdout': 'screen', 'stderr': 'screen'},
            )
        ]

    control_node = OpaqueFunction(
        function=_create_control_node,
        condition=IfCondition(
            PythonExpression([
                "'", sim, "' == 'false' and '", launch_hw, "' == 'true'"
            ])
        ),
    )

    control_node_delayed = TimerAction(
        period=1.0,
        actions=[control_node],
        condition=UnlessCondition(sim),
    )

    # Robot state publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        # namespace=namespace,
        output='both',
        parameters=[{'use_sim_time': sim}, robot_description]
    )

    # ----------------------- Multi-controller spawn -----------------------
    # Spawns the requested controllers AND the joint-state broadcaster.
    # For HW multi-robot the CM node name is e.g. right_controller_manager;
    # for sim (gazebo plugin) it stays 'controller_manager'.
    def spawn_controllers(context, *args, **kwargs):
        controllers_arg = LaunchConfiguration('robot_controller').perform(context)
        controllers = [c.strip() for c in controllers_arg.replace(',', ' ').split() if c.strip()]

        ns_raw = LaunchConfiguration('namespace').perform(context)
        sim_val = LaunchConfiguration('sim').perform(context)

        # Match the CM node name chosen by _create_control_node
        if sim_val == 'false' and ns_raw:
            cm_name = f'{ns_raw}controller_manager'
        else:
            cm_name = 'controller_manager'

        # When the CM node has a custom name (multi-robot), _create_control_node
        # already merges all controller params into the CM node.  Passing
        # --param-file here would set params_file on the CM, causing it to
        # re-read the YAML under the wrong node name and ending up with empty
        # joints / command_interfaces.  Only use -p when the CM keeps its
        # default name (sim / single-robot).
        model_val = LaunchConfiguration('model').perform(context)
        ctrl_file_val = LaunchConfiguration('controllers_file').perform(context)
        yaml_path = os.path.join(
            get_package_share_directory('denso_robot_moveit_config'),
            'robots', model_val, 'config', ctrl_file_val,
        )

        use_param_file = (cm_name == 'controller_manager')

        nodes = []
        for ctrl in controllers:
            spawn_args = [ctrl, '-c', cm_name]
            if use_param_file:
                spawn_args += ['-p', yaml_path]
            nodes.append(
                Node(
                    package='controller_manager',
                    executable='spawner',
                    arguments=spawn_args,
                    output='screen',
                )
            )

        # Joint state broadcaster
        jsb_name = f'{ns_raw}denso_joint_state_broadcaster'
        jsb_args = [jsb_name, '-c', cm_name]
        if use_param_file:
            jsb_args += ['-p', yaml_path]
        nodes.append(
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=jsb_args,
            )
        )

        return nodes



    controller_spawners = OpaqueFunction(function=spawn_controllers)

    start_spawners_on_hw = TimerAction(
        period=1.0,
        actions=[controller_spawners],
        condition=IfCondition(
            PythonExpression([
                "'", sim, "' == 'false' and '", launch_hw, "' == 'true'"
            ])
        ),
    )

    set_slave_after_spawners = TimerAction(
        period=1.0,  # give spawners time to 'Configured and activated ...'
        actions=[
            ExecuteProcess(
                cmd=['ros2','service','call','/left_vm60b1/ChangeMode',
                    'denso_robot_core_interfaces/srv/ChangeMode','{mode: 514}']
            ),
            ExecuteProcess(
                cmd=['ros2','service','call','/right_vm60b1/ChangeMode',
                    'denso_robot_core_interfaces/srv/ChangeMode','{mode: 514}']
            ),
        ],
        condition=UnlessCondition(sim),
    )


    # RViz
    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare(moveit_config_package), 'rviz', 'view_robot.rviz'])
    rviz_node = Node(
        package='rviz2',
        condition=IfCondition(launch_rviz),
        executable='rviz2',
        name='rviz2_moveit',
        output='log',
        arguments=['-d', rviz_config_file],
        parameters=[
            robot_description,
            robot_description_semantic,
            ompl_planning_pipeline_config,
            robot_description_kinematics
        ])

    # Static transform
    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_transform_publisher',
        output='log',
        arguments=[
            '--frame-id', 'world',
            '--child-frame-id', TextJoinSubstitution([namespace], 'base_link', '')
        ])

    # --- world file ---
    world_file = PathJoinSubstitution([
        FindPackageShare('dual_denso_arm_manipulation'),
        'worlds',
        'empty_with_attachment.world',  # contains <plugin filename="libgazebo_link_attacher.so"/>
    ])

    # --- make sure Gazebo can find IFRA plugin .so ---
    attacher_prefix = get_package_prefix('ros2_linkattacher')  # IFRA package name
    set_gz_plugin_path = SetEnvironmentVariable(
        name='GAZEBO_PLUGIN_PATH',
        value=f"{attacher_prefix}/lib:" + os.environ.get('GAZEBO_PLUGIN_PATH', '')
    )

    # --- start Gazebo with ROS init + factory (ROS <-> Gazebo bridge) ---
    gazebo = ExecuteProcess(
        condition=IfCondition(sim),
        cmd=[
            'gazebo', '--verbose',
            world_file,
            '-s', 'libgazebo_ros_init.so',
            '-s', 'libgazebo_ros_factory.so',
        ],
        output='screen'
    )

    # --- spawn the robot after Gazebo is up ---
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        condition=IfCondition(sim),
        arguments=['-topic', 'robot_description', '-entity', denso_robot_model],
        output='screen'
    )

    # Delay
    spawn_entity = TimerAction(period=2.0, actions=[spawn_robot])

    # Start controller spawners only AFTER the robot is spawned
    start_spawners_after_spawn = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_robot,
            on_exit=[controller_spawners]
        )
    )

    # slave_delay = Node(
    #     package='denso_robot_control',
    #     executable='denso_robot_control',
    #     name='denso_robot_control',
    #     output='screen',
    #     parameters=[{
    #         'auto_slave': True,      # or False
    #         'slave_delay_ms': 2000, 
    #     }],
    #     )


    # ----------------------- Nodes to start -----------------------
    nodes_to_start = [
        set_gz_plugin_path,  
        delay_env, 
        control_node, # tried delay, fail
        # slave_delay,
        move_group_node,
        rviz_node,
        static_tf,
        gazebo,
        spawn_entity,
        robot_state_publisher_node,
        # EITHER: let spawners wait (okay)
        # controller_spawners,
        # OR: start them after spawn (quieter logs):
        start_spawners_after_spawn,
        start_spawners_on_hw,
        # set_slave_after_spawners,
        # joint_state_broadcaster_spawner is now part of spawn_controllers
        # control_node_delayed,
    ]
    return LaunchDescription(declared_arguments + nodes_to_start)
