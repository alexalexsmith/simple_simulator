"""
simple sim tool to apply a simulation on selected controls in maya
Using nparticles or ncloth
use:
adjust settings
select controls
bake to locators constrained to the selected controls
if you like the results you can bake the locator animation
If you hate the results you can delete the locators
(perhaps the locators can be a custom simple sim node, so I can grab them easier)
"""

"""
build sim rig steps:
attach a locator or curve to each bone
attach the locator or curve to the original selection with parent constraints
add attributes to control the simulation

bake sim rig steps:

"""
import logging

from maya import cmds, mel

from simple_simulator import constraint_creation_utils
from simple_simulator.decorators import suspend_refresh

# TODO: add roll and twist to sim controller
class SimpleSimulationRigCreator(object):
    """class for creating simple simulation rig"""

    def __init__(self):
        self.name = None
        self.selections = None  # list[MayaNode]
        # R I G
        self.sim_controller = None
        self.curve = None
        self.bones = None  # MayaNodes
        self.blend_locators = None  # MayaNodes
        self.scale_locators = None # MayaNodes
        # S I M U L A T I O N  S T U F
        self.nucleus = None
        self.nhair = None
        self.follicle = None
        self.dynamic_curve = None
        self.dynamic_constraints = None  # MayaNodes
        # G R O U P S
        self.main_group = None
        self.show_group = None
        self.hide_group = None

    @suspend_refresh
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
        if len(selection) == 0:
            cmds.warning("Selection of 1 or more objects is required to create a simple simulation")
            return

        simulation_selection_objects = []
        for node in selection:
            selection_object = Selection(node)
            simulation_selection_objects.append(selection_object)

        self.selections = simulation_selection_objects

    def _create_groups(self):
        """create groups to organize the rig elements as they are created"""
        main_group = cmds.group(empty=True, name="{0}_SIMPLESIM".format(self.name))
        show_group = cmds.group(empty=True, name="show_group", parent=main_group)
        hide_group = cmds.group(empty=True, name="hide_group", parent=main_group)
        self.main_group = MayaNode(main_group)
        self.show_group = MayaNode(show_group)
        self.hide_group = MayaNode(hide_group)
        self.hide_group.set_visible(False)

    def _create_curve(self):
        """create the curve to be simulated"""
        points = []
        for selection in self.selections:
            points.append(selection.translation)
        curve = cmds.curve(p=points, bezier=False, degree=1)
        renamed_curve = cmds.rename(curve, "{0}_curve".format(self.name))
        self.curve = Curve(renamed_curve)

    def _create_bones(self):
        """create bone chain"""
        cmds.select(d=True)
        bones = []
        for selection in self.selections:
            name = "{0}_{1}_joint".format(self.name, selection.short_name)
            bone = cmds.joint(name=name, position=selection.translation)
            bones.append(MayaNode(node=bone))
        self.bones = MayaNodes(nodes=bones)

    def _create_blend_locators(self):
        """create locators at selection points"""
        locators = []
        for selection in self.selections:
            name = "{0}_{1}_blend_locator".format(self.name, selection.short_name)
            locator = cmds.spaceLocator(name=name, absolute=True)
            locators.append(MayaNode(node=locator[0]))
        self.blend_locators = MayaNodes(nodes=locators)

    def _create_scale_locators(self):
        """create locators at selection points"""
        locators = []
        for selection in self.selections:
            name = "{0}_{1}_scale_locator".format(self.name, selection.short_name)
            locator = cmds.spaceLocator(name=name, absolute=True)
            locators.append(MayaNode(node=locator[0]))
        self.scale_locators = MayaNodes(nodes=locators)

    def _create_dynamics(self):
        """make curve dynamic by creating all dynamic nodes"""
        # create nhair system node
        self.nhair = NHair(cmds.createNode('hairSystem'))

        # create nucleus node
        self.nucleus = Nucleus(cmds.createNode('nucleus', name="{0}_nucleus".format(self.name)))

        # connect nhair to nucleus
        cmds.connectAttr(self.nhair.current_state, self.nucleus.inputActive)
        cmds.connectAttr(self.nhair.start_state, self.nucleus.inputActiveStart)
        cmds.connectAttr(self.nucleus.outputObjects, self.nhair.next_state)
        cmds.connectAttr(self.nucleus.startFrame, self.nhair.start_frame)

        # create follicle
        self.follicle = Follicle(cmds.createNode('follicle'))
        cmds.connectAttr(self.curve.local, self.follicle.start_position)
        cmds.connectAttr(self.curve.world_matrix, self.follicle.start_position_matrix, f=True)
        cmds.connectAttr(self.nhair.output_hair, self.follicle.current_position)
        cmds.connectAttr(self.follicle.out_hair, self.nhair.input_hair)

        # create dynamic curve
        self.dynamic_curve = Curve(cmds.createNode('nurbsCurve'))  # NOTE: the curve cv's are not built yet
        cmds.connectAttr(self.follicle.out_curve, self.dynamic_curve.create)  # NOTE: the curve cv's are now built

        # create dynamic constraints
        dynamic_constraints = []
        for cv, selection in zip(self.dynamic_curve.get_curve_vectors(), self.selections):
            cmds.select(cv, replace=True)
            constraint_stuff = mel.eval("createNConstraint transform 0;")
            dynamic_constraint = DynamicConstraint(node=constraint_stuff[0])
            dynamic_constraint.set_name("{0}_blend".format(selection.short_name))
            dynamic_constraints.append(dynamic_constraint)
        self.dynamic_constraints = MayaNodes(dynamic_constraints)

    def _create_sim_controller(self):
        """create the sim controller for adjusting the simulation"""
        sim_controller_points = [
            (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (1, 0, 0), (0, 1.5, 0), (-1, 0, 0), (0, -1.5, 0),
            (0, 0, 1), (0, 1, 0), (0, 0, -1), (0, -1, 0), (0, 0, 1), (0, 1.5, 0), (0, 0, -1), (0, -1.5, 0),
            (0, 0, 1), (1, 0, 0), (0, 0, -1), (-1, 0, 0), (0, 0, 1), (1, 0, 0), (0, -1, 0), (1, 0, 0), (0, -1.5, 0)
        ]
        name = "{0}_sim_controller".format(self.name)
        self.sim_controller = SimulationController(node=cmds.curve(p=sim_controller_points, degree=1, name=name))
        self.sim_controller.set_translation(self.selections[0].translation)

    def _connect_rig_components(self):
        """constraint all the rig components together. Group everything accordingly"""
        # animate dynamic constraints location so they follow the original animation
        self._animate_blend_locators()
        # create and connect all the attributes to the user controller
        self._connect_simulation_controller()
        # create ik handles for joint chain
        self._connect_bones_to_dynamic_curve()
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
                startJoint=self.bones.nodes[0].short_name,
                endEffector=self.bones.nodes[-1].short_name,
                curve=self.dynamic_curve.long_name,
                createCurve=False,
            )
        cmds.parent(ik_handle[0], self.hide_group.long_name)

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
                     self.nucleus, self.nhair, self.dynamic_constraints,
                     self.main_group, self.show_group, self.hide_group]
        for rig_object in rig_setup:
            rig_object.delete_node()


class MayaNode(object):
    """Maya node class"""

    def __init__(self, node=None, *args, **kwargs):
        self.long_name = None
        self.namespace = None
        self.short_name = None
        self.shape = None
        self.visibility = None
        self._init_maya_node(node)

    def _init_maya_node(self, node):
        """init the maya node name
        :param str node: name of node"""
        transform = cmds.ls(node, long=True)[0]
        shape = None
        if cmds.objectType(transform) == "transform":
            # some nodes don't have a shape node under them
            test_shape = cmds.listRelatives(node, shapes=True)
            if test_shape:
                shape = test_shape[0]
        # Joints are very "special"
        elif cmds.objectType(transform) == "joint":
            pass
        else:
            # Some non transform nodes don't have a transform node above them (Nucleus),
            # I will handle those as a transform for simplicity
            test_transform = cmds.listRelatives(node, parent=True, fullPath=True)
            if test_transform:
                shape = node
                transform = test_transform[0]
        self.long_name = transform
        if ":" in self.long_name.split("|")[-1]:
            self.namespace = self.long_name.split("|")[-1].split(":")[0]
            self.short_name = self.long_name.split("|")[-1].split(":")[1]
        else:
            self.short_name = self.long_name.split("|")[-1]
        self.shape = shape

    def select(self):
        """select the node in viewport"""
        cmds.select(self.long_name, replace=True)

    def delete_node(self):
        """delete the node if it exists"""
        if self.long_name:
            if cmds.objExists(self.long_name):
                cmds.delete(self.long_name)

    def get_attribute(self, attribute, shape=False):
        """get the full path of the attribute. useful when setting and connection attributes
        :param str attribute: name of attribute
        :param bool shape: whether attribute belongs to shape
        :return str: full path of attribute"""
        node_name = self.long_name
        if shape:
            node_name = self.shape
        return "{0}.{1}".format(node_name, attribute)

    def set_parent(self, maya_node):
        """set the parent of this MayaNode
        :param MayaNode maya_node: node to set as parent"""
        new_name = cmds.parent(self.long_name, maya_node.long_name)
        #  update the long name to match the new path name
        self.long_name = cmds.ls(new_name, long=True)[0]
        return self

    def set_name(self, name):
        """set the name of the node
        :param str name: new name"""
        new_name = cmds.rename(self.long_name, name)
        self._init_maya_node(new_name)  # need to re init this node after name change

    def set_visible(self, option):
        """set the visibility
        :param bool option: set visible or not"""
        cmds.setAttr("{0}.visibility".format(self.long_name), option)

    def set_translation(self, translation):
        """set the translation of this node
        :param tuple(float, float, float) translation: translation position to set"""
        cmds.xform(self.long_name, translation=translation, worldSpace=True)
        return

    def refresh_name(self):
        """used to refresh the name if the long name is updated due to hierarchy change"""
        if cmds.objExists(self.long_name):
            return self
        self.long_name = cmds.ls(self.short_name, long=True)[0]
        return self


class MayaNodes(object):
    """list of MayaNode's object"""
    def __init__(self, nodes=None, *args, **kwargs):
        """:param list[MayaNode] nodes: list of MayaNode object"""
        self.nodes = nodes

    def delete_node(self):
        """delete all the nodes"""
        for node in self.nodes:
            node.delete_node()
        self.nodes = None

    def set_parent(self, maya_node):
        """set the parent of all the nodes"""
        updated_nodes = []
        for node in self.nodes:
            updated_node = node.set_parent(maya_node)
            updated_nodes.append(updated_node)
        if len(updated_nodes) > 0:
            self.nodes = updated_nodes

    def refresh_name(self):
        """refresh name of each node"""
        updated_nodes = []
        for node in self.nodes:
            updated_node = node.refresh_name()
            updated_nodes.append(updated_node)
        if len(updated_nodes) > 0:
            self.nodes = updated_nodes

    def get_node_names_list(self):
        """get the list of maya_node names in a list of strings"""
        str_list = []
        for node in self.nodes:
            str_list.append(node.long_name)
        return str_list


class Selection(MayaNode):
    """class to organize nodes and their positions for simple simulation rig creation"""

    def __init__(self, *args, **kwargs):
        super(Selection, self).__init__(*args, **kwargs)
        self.translation = None
        self.matrix = None
        self._init_position()

    def _init_position(self):
        """init the world position of the node"""
        if cmds.objExists(self.long_name):
            self.translation = cmds.xform(self.long_name, query=True, translation=True, worldSpace=True)
            self.matrix = cmds.xform(self.long_name, query=True, matrix=True, worldSpace=True)


class Curve(MayaNode):
    """class to organize a curve and it's curve vectors"""

    def __init__(self, *args, **kwargs):
        super(Curve, self).__init__(*args, **kwargs)
        self.local = "{0}.local".format(self.shape)
        self.create = "{0}.create".format(self.shape)
        self.world_matrix = "{0}.worldMatrix[0]".format(self.long_name)
        self.world_space = "{0}.worldSpace[0]".format(self.long_name)

    def get_curve_vectors(self):
        """init the curve vectors"""
        curve_vectors = cmds.ls('{0}.cv[:]'.format(self.short_name), flatten=True)
        return curve_vectors

    def uv_pin(self, maya_node, u_position):
        """uv pin a node to this curve
        :param MayaNode maya_node: node to attach
        :param float u_position: position to set connection to"""
        uv_pin = cmds.createNode("uvPin", name="{0}_uvPin".format(maya_node.short_name))
        cmds.connectAttr(self.world_space, "{0}.deformedGeometry".format(uv_pin))
        cmds.connectAttr("{0}.local".format(self.shape), "{0}.originalGeometry".format(uv_pin))
        cmds.setAttr("{0}.normalizedIsoParms".format(uv_pin), 0)
        cmds.setAttr("{0}.coordinate[0]".format(uv_pin), u_position, 0)
        cmds.connectAttr("{0}.outputMatrix[0]".format(uv_pin), "{0}.offsetParentMatrix".format(maya_node.long_name))


class NHair(MayaNode):
    """nhair object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(NHair, self).__init__(*args, **kwargs)
        self.current_state = "{0}.currentState".format(self.shape)
        self.start_state = "{0}.startState".format(self.shape)
        self.next_state = "{0}.nextState".format(self.shape)
        self.start_frame = "{0}.startFrame".format(self.shape)
        # TODO: this attribute needs dynamic indexing
        self.output_hair = "{0}.outputHair[0]".format(self.shape)
        self.input_hair = "{0}.inputHair[0]".format(self.shape)
        self.nucleus_id = "{0}.nucleusId".format(self.shape)

        self._set_up_nhair()

    def _set_up_nhair(self):
        """basic nhair setup"""
        # do some break instances thing
        cmds.removeMultiInstance("{0}.stiffnessScale[1]".format(self.shape), b=True)
        # set basic attributes of the nhair
        cmds.setAttr("{0}.clumpWidth".format(self.shape), 0.00001)
        cmds.setAttr("{0}.hairsPerClump".format(self.shape), 1)
        # connect time node to nhair
        cmds.connectAttr("time1.outTime", "{0}.currentTime".format(self.shape))
        # set nhair active
        cmds.setAttr("{0}.active".format(self.shape), 1)


class Nucleus(MayaNode):
    """nucleus object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(Nucleus, self).__init__(*args, **kwargs)
        # TODO: the attribute index needs to be dynamic based on the amount of hair connections.
        # This works but is sketchy
        self.inputActive = "{0}.inputActive[0]".format(self.long_name)
        self.inputActiveStart = "{0}.inputActiveStart[0]".format(self.long_name)
        self.outputObjects = "{0}.outputObjects[0]".format(self.long_name)
        self.startFrame = "{0}.startFrame".format(self.long_name)
        self.input_start = "{0}.inputStart[0]".format(self.long_name)
        self.input_current = "{0}.inputCurrent[0]".format(self.long_name)

        self._set_up_nucleus()

    def _set_up_nucleus(self):
        """basic nucleus setup"""
        cmds.connectAttr("time1.outTime", "{0}.currentTime".format(self.long_name))

    def force_dynamics(self):
        """force dynamics on the current frame"""
        cmds.getAttr("{0}.forceDynamics".format(self.long_name))


class Follicle(MayaNode):
    """Follicle node with some attributes"""

    def __init__(self, *args, **kwargs):
        super(Follicle, self).__init__(*args, **kwargs)
        self.start_position = "{0}.startPosition".format(self.shape)
        self.start_position_matrix = "{0}.startPositionMatrix".format(self.shape)
        self.current_position = "{0}.currentPosition".format(self.shape)
        self.out_curve = "{0}.outCurve".format(self.shape)
        self.out_hair = "{0}.outHair".format(self.shape)

        self._set_up_follicle()

    def _set_up_follicle(self):
        """basic follicle setup"""
        cmds.setAttr("{0}.pointLock".format(self.shape), 0)
        cmds.setAttr("{0}.degree".format(self.shape), 1)
        cmds.setAttr("{0}.startDirection".format(self.shape), 1)
        cmds.setAttr("{0}.simulationMethod".format(self.shape), 2)


class SimulationController(MayaNode):
    """Simulation controller object"""

    def __init__(self, *args, **kwargs):
        super(SimulationController, self).__init__(*args, **kwargs)
        self._set_up_simulation_controller()

    def _set_up_simulation_controller(self):
        """basic setup"""
        hide_attributes = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]
        for attribute in hide_attributes:
            cmds.setAttr("{0}.{1}".format(self.long_name, attribute), keyable=False, channelBox=False)

    def add_spacer_attribute(self, title):
        """add a spacer attribute
        :param str title: title of the spacer"""
        attribute_name = "{0}_Spacer".format(title)
        cmds.addAttr(
            self.long_name,
            attributeType="enum",
            hidden=False,
            keyable=False,
            longName=attribute_name,
            niceName="##########",
            enumName=title
        )
        cmds.setAttr("{0}.{1}".format(self.long_name, attribute_name), channelBox=True)

    def add_double_attribute(self, name, default_value):
        """add a double attribute that is visible in the attribute editor
        :param str name: name of attribute
        :param float default_value: default value of attribute"""
        cmds.addAttr(
            self.long_name,
            attributeType="double",
            longName=name,
            defaultValue=default_value,
            hidden=False,
            keyable=True
        )

    def attach_nucleus(self, nucleus):
        """attach a nucleus to the simulation controller
        :param Nucleus nucleus: Nucleus to connect"""
        self.add_spacer_attribute("NUCLEUS")
        start_frame = cmds.playbackOptions(query=True, minTime=True)
        attributes = {"startFrame": start_frame, "frameJumpLimit": 1, "spaceScale": 1}
        for attribute in attributes:
            self.add_double_attribute(attribute, attributes[attribute])
            cmds.connectAttr(self.get_attribute(attribute), nucleus.get_attribute(attribute))

    def attach_nhair(self, nhair):
        """attach nhair to the simulation controller
        :param NHair nhair: NHair to connect"""
        self.add_spacer_attribute("NHAIR")
        nhair_attributes = {"bounce": 0, "damp": 0, "drag": 0.05, "friction": 0.5,
                            "stickiness": 0, "stiffness": 0, "stretchResistance": 10,
                            "compressionResistance": 10, "collideWidthOffset": 0}
        for attribute in nhair_attributes:
            self.add_double_attribute(attribute, nhair_attributes[attribute])
            cmds.connectAttr(self.get_attribute(attribute), nhair.get_attribute(attribute, shape=True))

    def attach_dynamic_constraint(self, dynamic_constraint):
        """attach constraint node to sim controller. Add attribute for user control
        :param DynamicConstraint dynamic_constraint: DynamicConstraint to connect"""
        attribute = "{0}Strength".format(dynamic_constraint.short_name)
        self.add_double_attribute(attribute, 20)
        cmds.connectAttr(self.get_attribute(attribute), dynamic_constraint.get_attribute("strength", shape=True))


class DynamicConstraint(MayaNode):
    """dynamic constraint node"""

    def __init__(self, *args, **kwargs):
        super(DynamicConstraint, self).__init__(*args, **kwargs)
        self.strength = "{0}.strength".format(self.shape)
        self.component_ids = "{0}.componentIds".format(self.shape)
        self.eval_start = "{0}.evalStart[0]".format(self.shape)
        self.eval_current = "{0}.evalCurrent[0]".format(self.shape)

        #self._set_up_constraint()

    def _set_up_constraint(self):
        """basic dynamic constraint setup"""
        cmds.setAttr("{0}.constraintRelation".format(self.shape), 0)
        cmds.setAttr("{0}.componentRelation".format(self.shape), 0)
        cmds.connectAttr("time1.outTime", "{0}.currentTime".format(self.shape))