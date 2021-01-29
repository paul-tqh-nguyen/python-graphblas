import numpy as np
from . import ffi, lib
from .dtypes import lookup_dtype, _INDEX


def libget(name):
    """Helper to get items from GraphBLAS which might be GrB or GxB"""
    try:
        return getattr(lib, name)
    except AttributeError:
        ext_name = f"GxB_{name[4:]}"
        try:
            return getattr(lib, ext_name)
        except AttributeError:
            pass
        raise


def ints_to_numpy_buffer(array, dtype, *, name="array", copy=False, ownable=False, order="C"):
    if (
        isinstance(array, np.ndarray)
        and not np.issubdtype(array.dtype, np.integer)
        and not np.issubdtype(array.dtype, np.bool8)
    ):
        raise ValueError(f"{name} must be integers, not {array.dtype.name}")
    array = np.array(array, dtype, copy=copy, order=order)
    if ownable and (not array.flags.owndata or not array.flags.writeable):
        array = array.copy()
    return array


def values_to_numpy_buffer(array, dtype=None, *, copy=False, ownable=False, order="C"):
    if dtype is not None:
        dtype = lookup_dtype(dtype)
        array = np.array(array, dtype.np_type, copy=copy, order=order)
    else:
        is_input_np = isinstance(array, np.ndarray)
        array = np.array(array, copy=copy, order=order)
        if array.dtype == object:
            raise ValueError("object dtype for values is not allowed")
        if not is_input_np and array.dtype == np.int32:  # pragma: no cover
            # fix for win64 numpy handling of ints
            array = array.astype(np.int64)
        dtype = lookup_dtype(array.dtype)
    if ownable and (not array.flags.owndata or not array.flags.writeable):
        array = array.copy()
    return array, dtype


def get_shape(nrows, ncols, **arrays):
    if nrows is None or ncols is None:
        # Get nrows and ncols from the first 2d array
        arr = next((array for array in arrays.values() if array.ndim == 2), None)
        if arr is None:
            raise ValueError(
                "Either nrows and ncols must be provided, or one of the following arrays"
                f'must be 2d (from which to get nrows and ncols): {", ".join(arrays)}'
            )
        if nrows is None:
            nrows = arr.shape[0]
        if ncols is None:
            ncols = arr.shape[1]
    return nrows, ncols


# A similar object may eventually make it to the GraphBLAS spec.
# Hide this from the user for now.
class _CArray:
    def __init__(self, array=None, *, size=None, dtype=_INDEX, name=None):
        if size is not None:
            self.array = np.empty(size, dtype=dtype.np_type)
        else:
            self.array = np.array(array, dtype=dtype.np_type, copy=False, order="C")
        self._carg = ffi.cast(f"{dtype.c_type}*", ffi.from_buffer(self.array))
        self.dtype = dtype
        self._name = name

    @property
    def name(self):
        if self._name is not None:
            return self._name
        if len(self.array) < 20:
            values = ", ".join(map(str, self.array))
        else:
            values = (
                f"{', '.join(map(str, self.array[:5]))}, "
                "..., "
                f"{', '.join(map(str, self.array[-5:]))}"
            )
        return "(%s[]){%s}" % (self.dtype.c_type, values)


class _Pointer:
    def __init__(self, val):
        self.val = val

    @property
    def _carg(self):
        return self.val.gb_obj

    @property
    def name(self):
        name = self.val.name
        if not name:
            name = f"temp_{type(self.val).__name__.lower()}"
        return f"&{name}"
