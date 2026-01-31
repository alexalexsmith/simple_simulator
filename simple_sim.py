"""
simple sim tool to apply a simulation on selected controls in maya
Currently using nHair
TODO:
rig setup doesn't simulate roll. need to look into some solutions
-build offset secondary sim rig for main rig to calculate twist. may have strange behavior with colliders
"""

import logging

from maya import cmds, mel

from simple_simulator import constraint_creation_utils, maya_node_utils
from simple_simulator.decorators import suspend_refresh, undoable_chunk


class SimpleSimulationRigCreator(object):
    """class for creating simple simulation rig"""

    def __init__(self):
        self.name = None
        self.selections = None  # list[MayaNode]
        # R I G
        self.sim_controller = None
        self.curve = None
        self.roll_curve = None
        self.bones = None  # MayaNodes
        self.ik_handle = None
        self.blend_locators = None  # MayaNodes
        self.scale_locators = None # MayaNodes
        self.roll_locators = None
        # S I M U L A T I O N  S T U F F
        self.nucleus = None
        self.nhair = None
        self.follicle = None
        self.dynamic_curve = None
        self.dynamic_roll_curve = None
        self.dynamic_constraints = None  # MayaNodes
        # G R O U P S
        self.main_group = None
        self.show_group = None
        self.hide_group = None

    @suspend_refresh
    @undoable_chunk
    def create_rig(self, name="rig_01"):
        """create the rig
        :param str name: name of rig to create"""
        self.name = name

        self._get_selection()
        if not self.selections:
            cmds.warning("selection was not initiated correctly, rig cannot be created")
            return

        try:
            self._create_groups()
            self._create_curve()
            self._create_bones()
            self._create_blend_locators()
            self._create_scale_locators()
            self._create_dynamics()
            self._create_sim_controller()
            self._connect_rig_components()
        except Exception as e:
            logging.exception(e)
            self._delete_rig()

    def _get_selection(self):
        """get the current selection to create the rig"""
        selection = cmds.ls(selection=True)
        if len(selection) < 2:
            cmds.warning("Selection of 2 or more objects is required to create a simple simulation")
            return

        simulation_selection_objects = []
        for node in selection:
            selection_object = maya_node_utils.Selection(node)
            simulation_selection_objects.append(selection_object)

        self.selections = simulation_selection_objects

    def _create_groups(self):
        """create groups to organize the rig elements as they are created"""
        main_group = cmds.group(empty=True, name="{0}_SIMPLESIM".format(self.name))
        show_group = cmds.group(empty=True, name="show_group", parent=main_group)
        hide_group = cmds.group(empty=True, name="hide_group", parent=main_group)
        self.main_group = maya_node_utils.MayaNode(main_group)
        self.show_group = maya_node_utils.MayaNode(show_group)
        self.hide_group = maya_node_utils.MayaNode(hide_group)
        self.hide_group.set_visible(False)

    def _create_curve(self):
        """create the curve to be simulated"""
        points = []
        for selection in self.selections:
            points.append(selection.translation)
        curve = cmds.curve(p=points, bezier=False, degree=1)
        renamed_curve = cmds.rename(curve, "{0}_curve".format(self.name))
        self.curve = maya_node_utils.Curve(renamed_curve)

    def _create_bones(self):
        """create bone chain"""
        cmds.select(d=True)
        bones = []
        for selection in self.selections:
            name = "{0}_{1}_joint".format(self.name, selection.short_name)
            bone = cmds.joint(name=name, position=selection.translation)
            bones.append(maya_node_utils.MayaNode(node=bone))
        self.bones = maya_node_utils.MayaNodes(nodes=bones)

    def _create_blend_locators(self):
        """create locators at selection points"""
        locators = []
        for selection in self.selections:
            name = "{0}_{1}_blend_locator".format(self.name, selection.short_name)
            locator = cmds.spaceLocator(name=name, absolute=True)
            locators.append(maya_node_utils.MayaNode(node=locator[0]))
        self.blend_locators = maya_node_utils.MayaNodes(nodes=locators)

    def _create_scale_locators(self):
        """create locators at selection points"""
        locators = []
        for selection in self.selections:
            name = "{0}_{1}_scale_locator".format(self.name, selection.short_name)
            locator = cmds.spaceLocator(name=name, absolute=True)
            locators.append(maya_node_utils.MayaNode(node=locator[0]))
        self.scale_locators = maya_node_utils.MayaNodes(nodes=locators)

    def _create_dynamics(self):
        """make curve dynamic by creating all dynamic nodes"""
        # create nhair system node
        self.nhair = maya_node_utils.NHair(cmds.createNode('hairSystem'))

        # create nucleus node
        self.nucleus = maya_node_utils.Nucleus(cmds.createNode('nucleus', name="{0}_nucleus".format(self.name)))

        # connect nhair to nucleus
        cmds.connectAttr(self.nhair.current_state, self.nucleus.inputActive)
        cmds.connectAttr(self.nhair.start_state, self.nucleus.inputActiveStart)
        cmds.connectAttr(self.nucleus.outputObjects, self.nhair.next_state)
        cmds.connectAttr(self.nucleus.startFrame, self.nhair.start_frame)

        # create follicle
        self.follicle = maya_node_utils.Follicle(cmds.createNode('follicle'))
        cmds.connectAttr(self.curve.local, self.follicle.start_position)
        cmds.connectAttr(self.curve.world_matrix, self.follicle.start_position_matrix, f=True)
        cmds.connectAttr(self.nhair.output_hair, self.follicle.current_position)
        cmds.connectAttr(self.follicle.out_hair, self.nhair.input_hair)

        # create dynamic curve
        self.dynamic_curve = maya_node_utils.Curve(cmds.createNode('nurbsCurve'))  # NOTE: the curve cv's are not built yet
        cmds.connectAttr(self.follicle.out_curve, self.dynamic_curve.create)  # NOTE: the curve cv's are now built

        # create dynamic constraints
        dynamic_constraints = []
        for cv, selection in zip(self.dynamic_curve.get_curve_vectors(), self.selections):
            cmds.select(cv, replace=True)
            constraint_stuff = mel.eval("createNConstraint transform 0;")
            dynamic_constraint = maya_node_utils.DynamicConstraint(node=constraint_stuff[0])
            dynamic_constraint.set_name("{0}_blend".format(selection.short_name))
            dynamic_constraints.append(dynamic_constraint)
        self.dynamic_constraints = maya_node_utils.MayaNodes(dynamic_constraints)

    def _create_sim_controller(self):
        """create the sim controller for adjusting the simulation"""
        sim_controller_points = [
            (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (1, 0, 0), (0, 1.5, 0), (-1, 0, 0), (0, -1.5, 0),
            (0, 0, 1), (0, 1, 0), (0, 0, -1), (0, -1, 0), (0, 0, 1), (0, 1.5, 0), (0, 0, -1), (0, -1.5, 0),
            (0, 0, 1), (1, 0, 0), (0, 0, -1), (-1, 0, 0), (0, 0, 1), (1, 0, 0), (0, -1, 0), (1, 0, 0), (0, -1.5, 0)
        ]
        name = "{0}_sim_controller".format(self.name)
        self.sim_controller = maya_node_utils.SimulationController(node=cmds.curve(p=sim_controller_points, degree=1, name=name))
        self.sim_controller.set_translation(self.selections[0].translation)

    def _connect_rig_components(self):
        """constraint all the rig components together. Group everything accordingly"""
        # animate dynamic constraints location so they follow the original animation
        self._animate_blend_locators()
        # create ik handles for joint chain
        self._connect_bones_to_dynamic_curve()
        # create and connect all the attributes to the user controller
        self._connect_simulation_controller()
        # connect scale locators to dynamic curve
        self._connect_scale_locators_to_dynamic_curve()
        # connect the bones to the scale locators for stretching
        self._connect_bones_to_scale_locators()
        # connect the original selection to the rig
        self._connect_selection_to_rig()
        # select the simulation controller
        self.sim_controller.select()

        # group the rig
        self.curve.set_parent(self.hide_group)
        self.bones.nodes[0].set_parent(self.hide_group)
        self.bones.refresh_name()  # need to refresh the bone chain names because they are parented to each other
        self.blend_locators.set_parent(self.hide_group)
        self.ik_handle.set_parent(self.hide_group)
        self.scale_locators.set_parent(self.hide_group)
        self.nucleus.set_parent(self.hide_group)
        self.dynamic_curve.set_parent(self.hide_group)
        self.nhair.set_parent(self.hide_group)
        self.follicle.set_parent(self.hide_group)
        self.dynamic_constraints.set_parent(self.hide_group)
        self.sim_controller.set_parent(self.show_group)

    def _connect_simulation_controller(self):
        """connect the simulation controller"""
        # attach sim controller to the top of the selection
        constraint_creation_utils.create_parent_constraint(
            parent=self.selections[0].long_name,
            child=self.sim_controller.long_name
        )
        self.sim_controller.attach_nucleus(self.nucleus)
        self.sim_controller.attach_ik_handle(self.ik_handle)
        self.sim_controller.attach_nhair(self.nhair)
        self.sim_controller.add_spacer_attribute("BLEND")
        for dynamic_constraint in self.dynamic_constraints.nodes:
            self.sim_controller.attach_dynamic_constraint(dynamic_constraint)

    def _connect_scale_locators_to_dynamic_curve(self):
        """connect locators to dynamic curve using the UV Pin node"""
        for u_position, locator in enumerate(self.scale_locators.nodes):
            self.dynamic_curve.uv_pin(locator, u_position)

    def _connect_bones_to_dynamic_curve(self):
        """connect the bone chain to the dynamic curve via ik handle"""
        ik_handle = cmds.ikHandle(
                solver="ikSplineSolver",
                startJoint=self.bones.nodes[0].long_name,
                endEffector=self.bones.nodes[-1].long_name,
                curve=self.dynamic_curve.long_name,
                createCurve=False,
            )
        # store ik handle as maya node to attach to the simulation controller
        self.ik_handle = maya_node_utils.MayaNode(ik_handle[0])

    def _connect_bones_to_scale_locators(self):
        """connect the bones to the scale locators"""
        for index in range(len(self.scale_locators.nodes)-1):
            distance_node = cmds.createNode('distanceDimShape')
            math_node = cmds.createNode('multiplyDivide')
            cmds.connectAttr(
                "{0}.worldPosition[0]".format(self.scale_locators.nodes[index].shape),
                "{0}.startPoint".format(distance_node),
                force=True)
            cmds.connectAttr(
                "{0}.worldPosition[0]".format(self.scale_locators.nodes[index+1].shape),
                "{0}.endPoint".format(distance_node),
                force=True)
            rest_distance = cmds.getAttr("{0}.distance".format(distance_node))
            cmds.setAttr("{0}.input2Y".format(math_node), rest_distance)
            cmds.setAttr("{0}.operation".format(math_node), 2)
            cmds.connectAttr(
                "{0}.distance".format(distance_node),
                "{0}.input1Y".format(math_node),
                force=True)
            cmds.connectAttr(
                "{0}.outputY".format(math_node),
                "{0}.scaleY".format(self.bones.nodes[index].long_name),
                force=True)
            # this is fine to just hide without turning into maya node instance
            cmds.parent(distance_node, self.hide_group.long_name)

    def _connect_selection_to_rig(self):
        """Connect the selection to the rig"""
        for selection, locator, bone in zip(self.selections, self.blend_locators.nodes, self.bones.nodes):
            constraint_creation_utils.create_parent_constraint(
                parent=bone.long_name,
                child=locator.long_name,
                maintain_offset=False
            )
            constraint_creation_utils.create_scale_constraint(
                parent=bone.long_name,
                child=locator.long_name,
            )
            constraint_creation_utils.create_parent_constraint(
                parent=locator.long_name,
                child=selection.long_name
            )

    def _animate_blend_locators(self):
        """animate all the blend locators"""
        parent_constraints = []
        for dynamic_constraint, selection in zip(self.dynamic_constraints.nodes, self.selections):
            constraint_creation_utils.create_parent_constraint(
                parent=selection.long_name,
                child=dynamic_constraint.long_name
            )
        # bake animation to constraint nodes
        min_time = cmds.playbackOptions(query=True, minTime=True)
        max_time = cmds.playbackOptions(query=True, maxTime=True)
        attributes = ["tx", "ty", "tz", "rx", "ry", "rz"]
        # NOTE: baking the dynamic constraints will remove the parentConstraint node we created earlier
        cmds.bakeResults(
            self.dynamic_constraints.get_node_names_list(),
            attribute=attributes,
            time=(min_time, max_time),
            simulation=True)

    def _delete_rig(self):
        """for safety, we can delete anything that was created if the rig fails to create at some point"""
        rig_setup = [self.sim_controller, self.curve, self.bones, self.blend_locators,
                     self.nucleus, self.nhair, self.dynamic_constraints, self.scale_locators,
                     self.main_group, self.show_group, self.hide_group]
        for rig_object in rig_setup:
            if rig_object is None:
                continue
            rig_object.delete_node()
