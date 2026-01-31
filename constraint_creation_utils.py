"""constraint utilities. Creates constraints and avoids a lot of the errors that cancel creation"""

import maya.cmds as cmds

from simple_simulator.decorators import set_pref_anim_blend_with_existing_connections


# Constraint arg handler stuff
def get_locked_transforms(item):
    """get locked transforms of passed item
    :param str item: name of object to check
    :return [list,list,list]: translate rotate and scale locked axis ex: ['tx','ty'],['ry'],['sx','sy','sz']"""
    locked_translate=[]
    locked_rotate=[]
    locked_scale = []
    attribute_lists = {"t": locked_translate, "r": locked_rotate, "s": locked_scale}

    for attribute in ["t", "r", "s"]:
        for axis in ["x", "y", "z"]:
            if cmds.getAttr("{0}.{1}{2}".format(item, attribute, axis), lock=True):
                attribute_lists[attribute].append(axis)

    return locked_translate, locked_rotate, locked_scale


def _handle_skip_attributes_per_child(child, skip_translate=[], skip_rotate=[], skip_scale=[]):
    """handle the skip attribute per child"""

    skip_translate_arg, skip_rotate_arg, skip_scale_arg = skip_translate[:], skip_rotate[:], skip_scale[:]

    locked_t, locked_r, locked_s = get_locked_transforms(child)
    for locked_attr, skip_attribute in zip((locked_t,locked_r,locked_s),(skip_translate_arg,skip_rotate_arg,skip_scale_arg)):
        for axis in locked_attr:
            if axis not in skip_attribute:
                skip_attribute.append(axis)
    return skip_translate_arg, skip_rotate_arg, skip_scale_arg


# Constraint Functions
@set_pref_anim_blend_with_existing_connections
def create_parent_constraint(parent=None, child=None, maintain_offset=True, skip_translate=[], skip_rotate=[], **kwargs):
    """create parent constraint
    :param str parent: parent of constraint
    :param str child: child of constraint
    :param bool maintain_offset: maintain current offset
    :param list skip_translate: translate attributes to skip
    :param list skip_rotate:rotate attributes to skip
    :return str constraint: constraint created"""
    skip_translate_arg, skip_rotate_arg, skip_scale_arg = _handle_skip_attributes_per_child(
        child,
        skip_translate=skip_translate,
        skip_rotate=skip_rotate)
    constraint = cmds.parentConstraint(parent,
                                       child,
                                       maintainOffset=maintain_offset,
                                       skipTranslate=skip_translate_arg,
                                       skipRotate=skip_rotate_arg)
    return constraint


@set_pref_anim_blend_with_existing_connections
def create_point_constraint(parent=None, child=None, maintain_offset=True, skip_translate=[], **kwargs):
    """create point constraint
    :param str parent: parent of constraint
    :param str child: child of constraint
    :param bool maintain_offset: maintain current offset
    :param list skip_translate: translate attributes to skip
    :return str constraint: constraint created"""
    skip_translate_arg, skip_rotate_arg, skip_scale_arg = _handle_skip_attributes_per_child(
        child,
        skip_translate=skip_translate)
    constraint = cmds.pointConstraint(parent, child, maintainOffset=maintain_offset, skip=skip_translate_arg)

    return constraint


@set_pref_anim_blend_with_existing_connections
def create_orient_constraint(parent=None, child=None, maintain_offset=True, skip_rotate=[], **kwargs):
    """create orient constraint
    :param str parent: parent of constraint
    :param str child: child of constraint
    :param bool maintain_offset: maintain current offset
    :param list skip_rotate:rotate attributes to skip
    :return str constraint: constraint created"""
    skip_translate_arg, skip_rotate_arg, skip_scale_arg = _handle_skip_attributes_per_child(
        child,
        skip_rotate=skip_rotate)
    constraint = cmds.orientConstraint(parent, child, maintainOffset=maintain_offset, skip=skip_rotate_arg)

    return constraint


@set_pref_anim_blend_with_existing_connections
def create_scale_constraint(parent=None, child=None, maintain_offset=True, skip_scale=[], **kwargs):
    """create scale constraint
    :param str parent: parent of constraint
    :param str child: child of constraint
    :param bool maintain_offset: maintain current offset
    :param list skip_scale: scale attributes to skip
    :return str constraint: constraint created"""
    skip_translate_arg, skip_rotate_arg, skip_scale_arg = _handle_skip_attributes_per_child(
        child,
        skip_scale=skip_scale)
    constraint = cmds.scaleConstraint(parent, child, maintainOffset=maintain_offset, skip=skip_scale_arg)

    return constraint


@set_pref_anim_blend_with_existing_connections
def create_aim_constraint(parent=None, child=None, maintain_offset=True, skip_rotate=[], **kwargs):
    """create scale constraint
    :param str parent: parent of constraint
    :param str child: child of constraint
    :param bool maintain_offset: maintain current offset
    :param list skip_rotate: scale attributes to skip
    :return str constraint: constraint created"""
    skip_translate_arg, skip_rotate_arg, skip_scale_arg = _handle_skip_attributes_per_child(
        child,
        skip_scale=skip_rotate)
    constraint = cmds.aimConstraint(parent, child, maintainOffset=maintain_offset, skip=skip_rotate_arg)

    return constraint
