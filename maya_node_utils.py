"""
maya node module.
used to manage maya node names,attributes, and connections
"""

from maya import cmds


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
            self.namespace = self.long_name.split("|")[-1].rsplit(":", 1)[0]
            self.short_name = self.long_name.split("|")[-1].rsplit(":", 1)[1]
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

    def init_attributes(self):
        """
        init attributes, function is triggered when set_parent function is used to make sure stored attribute names
        remain accurate
        """
        return None

    def get_attribute(self, attribute, shape=False, next_index=False, index_range=100):
        """get the full path of the attribute. useful when setting and connection attributes
        :param str attribute: name of attribute
        :param bool shape: whether attribute belongs to shape
        :param bool next_index: if true will return the next available indexed plug
        :param int index_range: max range to check for indexed attribute plugs
        :return str: full path of attribute"""
        node_name = self.long_name
        if shape:
            node_name = self.shape
        attribute = f"{node_name}.{attribute}"
        if next_index:
            for i in range(index_range):
                connected = cmds.connectionInfo(f"{attribute}[{i}]", sourceFromDestination=True)
                if not connected:
                    attribute = f"{attribute}[{i}]"
                    break

        return attribute

    def set_parent(self, maya_node):
        """set the parent of this MayaNode
        :param MayaNode maya_node: node to set as parent"""
        new_name = cmds.parent(self.long_name, maya_node.long_name)
        #  update the long name to match the new path name
        self.long_name = cmds.ls(new_name, long=True)[0]
        self.init_attributes()
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
        self.local = None
        self.create = None
        self.world_matrix = None
        self.world_space = None

        self.init_attributes()

    def init_attributes(self):
        """
        init important attributes
        """
        self.local = self.get_attribute("local", shape=True)
        self.create = self.get_attribute("create", shape=True)
        self.world_matrix = self.get_attribute("worldMatrix", next_index=True, index_range=100)
        self.world_space = self.get_attribute("worldSpace", next_index=True, index_range=100)

    def get_curve_vectors(self):
        """init the curve vectors"""
        curve_vectors = cmds.ls('{0}.cv[:]'.format(self.short_name), flatten=True)
        return curve_vectors

    def uv_pin(self, maya_node, u_position):
        """uv pin a node to this curve
        :param MayaNode maya_node: node to attach
        :param float u_position: position to set connection to"""
        uv_pin = MayaNode(node=cmds.createNode("uvPin", name=f"{maya_node.short_name}_uvPin"))
        cmds.connectAttr(self.world_space, uv_pin.get_attribute("deformedGeometry"))
        cmds.connectAttr(self.get_attribute("local", shape=True), uv_pin.get_attribute("originalGeometry"))
        cmds.setAttr(uv_pin.get_attribute("normalizedIsoParms"), 0)
        cmds.setAttr(uv_pin.get_attribute("coordinate", next_index=True), u_position, 0)
        cmds.connectAttr(uv_pin.get_attribute("outputMatrix", next_index=True),
                         maya_node.get_attribute("offsetParentMatrix"))


class NHair(MayaNode):
    """nhair object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(NHair, self).__init__(*args, **kwargs)
        self.current_state = None
        self.start_state = None
        self.next_state = None
        self.start_frame = None
        self.output_hair = None
        self.input_hair = None
        self.nucleus_id = None

        self.init_attributes()
        self._set_up_nhair()

    def init_attributes(self):
        self.current_state = self.get_attribute("currentState", shape=True)
        self.start_state = self.get_attribute("startState", shape=True)
        self.next_state = self.get_attribute("nextState", shape=True)
        self.start_frame = self.get_attribute("startFrame", shape=True)
        self.output_hair = self.get_attribute("outputHair", shape=True, next_index=True, index_range=100)
        self.input_hair = self.get_attribute("inputHair", shape=True, next_index=True, index_range=100)
        self.nucleus_id = self.get_attribute("nucleusId", shape=True)

    def _set_up_nhair(self):
        """basic nhair setup"""
        # do some break instances thing
        cmds.removeMultiInstance("{0}.stiffnessScale[1]".format(self.shape), b=True)
        # set basic attributes of the nhair
        cmds.setAttr(self.get_attribute("clumpWidth", shape=True), 0.00001)
        cmds.setAttr(self.get_attribute("hairsPerClump", shape=True), 1)
        # connect time node to nhair
        cmds.connectAttr("time1.outTime", self.get_attribute("currentTime", shape=True))
        # set nhair active
        cmds.setAttr(self.get_attribute("active", shape=True), 1)


class Nucleus(MayaNode):
    """nucleus object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(Nucleus, self).__init__(*args, **kwargs)
        self.inputActive = None
        self.inputActiveStart = None
        self.outputObjects = None
        self.startFrame = None
        self.input_start = None
        self.input_current = None

        self.init_attributes()
        self._set_up_nucleus()

    def init_attributes(self):
        self.inputActive = self.get_attribute("inputActive", next_index=True, index_range=100)
        self.inputActiveStart = self.get_attribute("inputActiveStart", next_index=True, index_range=100)
        self.outputObjects = self.get_attribute("outputObjects", next_index=True, index_range=100)
        self.startFrame = self.get_attribute("startFrame")
        self.input_start = self.get_attribute("inputStart", next_index=True, index_range=100)
        self.input_current = self.get_attribute("inputCurrent", next_index=True, index_range=100)

    def _set_up_nucleus(self):
        """basic nucleus setup"""
        cmds.connectAttr("time1.outTime", self.get_attribute("currentTime"))

    def force_dynamics(self):
        """force dynamics on the current frame"""
        cmds.getAttr(self.get_attribute("forceDynamics"))

    def add_colliders(self, maya_node_list):
        """
        add collider objects to nucleus
        :param list[maya_node]: list of maya nodes
        """
        for maya_node in maya_node_list:
            n_rigid_node = MayaNode(node=cmds.createNode("nRigid"))
            cmds.connectAttr(
                "time1.outTime",
                n_rigid_node.get_attribute("currentTime"))
            cmds.connectAttr(
                maya_node.get_attribute("worldMesh", shape=True),
                n_rigid_node.get_attribute("inputMesh"))
            cmds.connectAttr(
                self.startFrame,
                n_rigid_node.get_attribute("startFrame"))
            cmds.connectAttr(
                n_rigid_node.get_attribute("currentState"),
                self.get_attribute("inputPassive", next_index=True))
            cmds.connectAttr(
                n_rigid_node.get_attribute("startState"),
                self.get_attribute("inputPassiveStart", next_index=True))

            cmds.setAttr(maya_node.get_attribute("quadSplit", shape=True), 0)


class Follicle(MayaNode):
    """Follicle node with some attributes"""

    def __init__(self, *args, **kwargs):
        super(Follicle, self).__init__(*args, **kwargs)
        self.start_position = None
        self.start_position_matrix = None
        self.current_position = None
        self.out_curve = None
        self.out_hair = None

        self.init_attributes()
        self._set_up_follicle()

    def init_attributes(self):
        self.start_position = self.get_attribute("startPosition", shape=True)
        self.start_position_matrix = self.get_attribute("startPositionMatrix", shape=True)
        self.current_position = self.get_attribute("currentPosition", shape=True)
        self.out_curve = self.get_attribute("outCurve", shape=True)
        self.out_hair = self.get_attribute("outHair", shape=True)

    def _set_up_follicle(self):
        """basic follicle setup"""
        cmds.setAttr(self.get_attribute("pointLock", shape=True), 0)
        cmds.setAttr(self.get_attribute("degree", shape=True), 1)
        cmds.setAttr(self.get_attribute("startDirection", shape=True), 1)
        cmds.setAttr(self.get_attribute("simulationMethod", shape=True), 2)


class SimulationController(MayaNode):
    """Simulation controller object"""

    def __init__(self, *args, **kwargs):
        super(SimulationController, self).__init__(*args, **kwargs)
        self._set_up_simulation_controller()
        self.dynamic_constraint_attributes = []

    def _set_up_simulation_controller(self):
        """basic setup"""
        hide_attributes = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]
        for attribute in hide_attributes:
            cmds.setAttr(self.get_attribute(attribute), keyable=False, channelBox=False)

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
        cmds.setAttr(self.get_attribute(attribute_name), channelBox=True)

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

    def attach_ik_handle(self, ik_handle):
        """attach an ik handle node to the simulation controller
        :param MayaNode ik_handle: ik handle to connect"""
        self.add_spacer_attribute("IK_Handle")
        ik_handle_attributes = {"roll": 0, "twist": 0}
        for attribute in ik_handle_attributes:
            self.add_double_attribute(attribute, ik_handle_attributes[attribute])
            cmds.connectAttr(self.get_attribute(attribute), ik_handle.get_attribute(attribute, shape=False))

    def attach_nhair(self, nhair):
        """attach nhair to the simulation controller
        :param NHair nhair: NHair to connect"""
        self.add_spacer_attribute("NHAIR")
        # TODO: selfCollide needs to ba a bool not a double
        nhair_attributes = {"selfCollide": 1, "bounce": 0, "damp": 0, "drag": 0.05, "friction": 0.5,
                            "stickiness": 0, "stiffness": 0, "stretchResistance": 10,
                            "compressionResistance": 10, "collideWidthOffset": 0}
        for attribute in nhair_attributes:
            self.add_double_attribute(attribute, nhair_attributes[attribute])
            cmds.connectAttr(self.get_attribute(attribute), nhair.get_attribute(attribute, shape=True))

    def attach_dynamic_constraint(self, dynamic_constraint):
        """attach constraint node to sim controller. Add attribute for user control
        :param DynamicConstraint dynamic_constraint: DynamicConstraint to connect
        :return str: name of attribute created"""
        attribute = "{0}Strength".format(dynamic_constraint.short_name)
        self.add_double_attribute(attribute, 20)
        cmds.connectAttr(self.get_attribute(attribute), dynamic_constraint.get_attribute("strength", shape=True))
        self.dynamic_constraint_attributes.append(attribute)
        return attribute


class DynamicConstraint(MayaNode):
    """dynamic constraint node"""

    def __init__(self, *args, **kwargs):
        super(DynamicConstraint, self).__init__(*args, **kwargs)
        self.strength = None
        self.component_ids = None
        self.eval_start = None
        self.eval_current = None

        self.init_attributes()
        # self._set_up_constraint()

    def init_attributes(self):
        self.strength = self.get_attribute("strength", shape=True)
        self.component_ids = self.get_attribute("componentIds", shape=True)
        self.eval_start = self.get_attribute("evalStart", shape=True, next_index=True, index_range=100)
        self.eval_current = self.get_attribute("evalCurrent", shape=True, next_index=True, index_range=100)

    def _set_up_constraint(self):
        """basic dynamic constraint setup"""
        cmds.setAttr(self.get_attribute("constraintRelation", shape=True), 0)
        cmds.setAttr(self.get_attribute("componentRelation", shape=True), 0)
        cmds.connectAttr("time1.outTime", self.get_attribute("currentTime", shape=True))
