from sqlalchemy.ext.mutable import Mutable


class MutableList(Mutable, list):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList."""

        if not isinstance(value, MutableList):
            if isinstance(value, list):
                return MutableList(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def __setitem__(self, key, value):
        """Detect list set events and emit change events."""

        list.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key):
        """Detect list del events and emit change events."""

        list.__delitem__(self, key)
        self.changed()
