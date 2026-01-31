"""maya node utils for handling maya nodes as scriptable objects"""

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
        # Some non transform nodes don't have a transform node above them (Nucleus, Joints)
        elif cmds.objectType(transform) in ["nucleus", "joint"]:
            pass
        # Finally we accept the passed node as a shape, and we get the transform above it
        else:
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

    def add_message_attribute(self, name):
        """add a message attribute to connect nodes to. This is used to store a relationship between nodes
        :param str name: name of new attribute
        :return str: full path of new attribute"""
        cmds.addAttr(self.long_name, keyable=False, attributeType="message", longName=name)
        return self.get_attribute(name)  # hopefully this will return the attribute

    def add_string_attribute(self, name, value):
        """add a string attribute with a value. This is used to tag nodes and hold constant name data
        :param str name: name of new attribute
        :param str value: value of new attribute
        :return str: full path of new attribute"""
        cmds.addAttr(self.long_name, keyable=False, dataType="string", longName=name)
        string_attribute = self.get_attribute(name)
        cmds.setAttr(string_attribute, value, type="string")
        return string_attribute

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
        # TODO: if attribute is multiindex I can grab the next available index value
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
        """set the translation of this node in world space
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
        # TODO: Remove these hard codes and use the get_attribute method from inherited class
        self.local = "{0}.local".format(self.shape)
        self.create = "{0}.create".format(self.shape)
        self.world_matrix = ".worldMatrix[0]".format(self.long_name)

    def get_curve_vectors(self):
        """init the curve vectors"""
        curve_vectors = cmds.ls('{0}.cv[:]'.format(self.short_name), flatten=True)
        return curve_vectors

    def attach_follicle(self, follicle):
        """attach curve to follicle. WARNING this is only for empty curve nodes
        :param Follicle follicle: node to connect"""
        cmds.connectAttr(
            follicle.get_attribute("outCurve", shape=True),
            self.get_attribute("create", shape=True))


class NHair(MayaNode):
    """nhair object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(NHair, self).__init__(*args, **kwargs)
        self.current_state = "{0}.currentState".format(self.shape)
        self.start_state = "{0}.startState".format(self.shape)
        self.next_state = "{0}.nextState".format(self.shape)
        self.start_frame = "{0}.startFrame".format(self.shape)
        # TODO: Remove these hard codes and use the get_attribute method from inherited class
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

    def connect_to_nucleus(self, nucleus):
        """connect nhair to nucleus
        :param Nucleus nucleus: nucleus to connect"""
        cmds.connectAttr(
            self.get_attribute("currentState", shape=True),
            nucleus.get_attribute("inputActive[0]"))
        cmds.connectAttr(
            self.get_attribute("startState", shape=True),
            nucleus.get_attribute("inputActiveStart[0]"))
        cmds.connectAttr(
            nucleus.get_attribute("outputObjects[0]"),
            self.get_attribute("nextState", shape=True))
        cmds.connectAttr(
            nucleus.get_attribute("startFrame"),
            self.get_attribute("startFrame", shape=True))


class Nucleus(MayaNode):
    """nucleus object with some attributes"""

    def __init__(self, *args, **kwargs):
        super(Nucleus, self).__init__(*args, **kwargs)
        # TODO: Remove these hard codes and use the get_attribute method from inherited class
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

    def connect_to_curve(self, curve):
        """connect to curve
        :param Curve curve: object to connect"""
        cmds.connectAttr(
            curve.get_attribute("local", shape=True),
            self.get_attribute("startPosition", shape=True))
        cmds.connectAttr(
            curve.get_attribute("worldMatrix[0]", shape=True),
            self.get_attribute("startPositionMatrix", shape=True),
            f=True)

    def connect_nhair(self, nhair):
        """connect nhair
        :param NHair nhair: nhair to connect"""
        cmds.connectAttr(
            nhair.get_attribute("outputHair[0]", shape=True),
            self.get_attribute("currentPosition", shape=True))
        cmds.connectAttr(
            self.get_attribute("outHair", shape=True),
            nhair.get_attribute("inputHair[0]", shape=True))


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
    # NOTE: this is here in case I want to create the dynamic transform constraints myself later
    def _set_up_constraint(self):
        """basic dynamic constraint setup"""
        cmds.setAttr("{0}.constraintRelation".format(self.shape), 0)
        cmds.setAttr("{0}.componentRelation".format(self.shape), 0)
        cmds.connectAttr("time1.outTime", "{0}.currentTime".format(self.shape))
