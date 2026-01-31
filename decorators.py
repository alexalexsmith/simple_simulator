"""decorators"""
from functools import wraps

from maya import cmds


def undoable_chunk(func):
    """Puts the wrapped `func` into a single Maya Undo action."""

    @wraps(func)
    def _wrapper_undoable_chunk(*args, **kwargs):
        # start an undo chunk
        cmds.undoInfo(openChunk=True)
        try:
            return func(*args, **kwargs)
        except Exception:
            raise  # will raise original error
        finally:
            # after calling the func, end the undo chunk
            cmds.undoInfo(closeChunk=True)

    return _wrapper_undoable_chunk


def suspend_refresh(func):
    """ Decorator to suspend the refresh when executing func
    More info at: https://www.toadstorm.com/blog/?p=424"""

    @wraps(func)
    def _wrapper_suspend_refresh(*args, **kwargs):
        # Suspend refresh
        cmds.refresh(suspend=True)
        try:
            # Execute the function
            return func(*args, **kwargs)
        except Exception:
            raise  # will raise original error
        finally:
            # reactivate refresh
            cmds.refresh(suspend=False)

    return _wrapper_suspend_refresh


def set_pref_anim_blend_with_existing_connections(func):
    """ Decorator to change the 'animBlendingOpt' preference to 'blend with existing connections' when executing func.
    The initial user preferences are restored after the execution of func.
    """

    @wraps(func)
    def _wrapper_set_anim_blend_with_existing_connections(*args, **kwargs):
        # Store initial blending options
        initial_blending_options = cmds.optionVar(query="animBlendingOpt")
        # Set blending options to blend with existing connections
        cmds.optionVar(intValue=("animBlendingOpt",1))

        try:
            # Execute the function
            return func(*args, **kwargs)
        except Exception:
            raise  # will raise original error
        finally:
            # restore original blending options
            cmds.optionVar(intValue=("animBlendingOpt", initial_blending_options))

    return _wrapper_set_anim_blend_with_existing_connections
