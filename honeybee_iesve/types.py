# coding=utf-8
"""Enumeration-style container for different object types in GEM."""


class _GemType(object):
    """Represents a single GEM object type with Enum-like .name and .value attributes."""

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def _get_numeric_values(self, index):
        return int(self.value.split('-')[index])

    def category(self):
        return self._get_numeric_values(0)

    def type(self):
        return self._get_numeric_values(1)

    def subtype(self):
        return self._get_numeric_values(2)

    def layer(self):
        return self._get_numeric_values(3)

    def color(self, rgb=False):
        return self._get_numeric_values(5) \
            if rgb else self._get_numeric_values(4)

    def keyword(self):
        return self.value.split('-')[-1]

    def to_gem(
            self, name, identifier, vertices, faces='',
            vertices_count=0, face_count=0):
        """Get a formatted GEM string."""
        full_name = name if not identifier else '{} [{}]'.format(name, identifier)

        gem_header = (
            'LAYER\n{}\n'
            'COLOUR\n{}\n'
            'CATEGORY\n{}\n'
            'TYPE\n{}\n'
            'SUBTYPE\n{}\n'
            'COLOURRGB\n{}\n'
            '{} {}\n'
        ).format(
            self.layer(),
            self.color(),
            self.category(),
            self.type(),
            self.subtype(),
            self.color(True),
            self.keyword(),
            full_name
        )

        if self.name in ('Tree', 'PV'):
            gem_str = gem_header + '{}'.format(vertices)
            return gem_str
        else:
            gem_str = gem_header + '{} {}\n{}\n{}'.format(
                vertices_count, face_count, vertices, faces
            )
        if self.name == 'TranslucentShade':
            gem_str = '\n'.join(gem_str.split('\n')[:-1])
            gem_str += '\n1\n{} 0\n{}'.format(vertices_count, vertices)

        return gem_str

    def __eq__(self, other):
        if isinstance(other, _GemType):
            return self.value == other.value
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.name, self.value))

    def __repr__(self):
        return '<GEM_TYPES.{}: {!r}>'.format(self.name, self.value)


class GEM_TYPES(object):
    """Enumeration-style container for different object types in GEM.

    There is no public documentation for GEM files but here is our understanding based
    on the sample files.

    -----------------------------------------------------------------------------------
    |     object     | CATEGORY | TYPE | SUBTYPE | LAYER | COLOR | COL-RGB  | KEYWORD |
    -----------------------------------------------------------------------------------
    |  Rooms/Spaces  |    1     |  1   |   2001  |   1   |   0   | 16711680 |   IES   |
    |  UnCond Space  |    1     |  1   |   2002  |   1   |   0   | 16711680 |   IES   |
    |  Trans Shades  |    1     |  1   |   2102  |  64   |   0   |    0     |   IES   |
    |   Nghbr Bldg   |    1     |  2   |    0    |  62   |   0   | 16711935 |   IES   |
    |       PV       |    3     | 202  |    0    |   1   |   0   |  32767   |   PVP   |
    |      Tree      |    1     |  3   |    0    |  65   |   0   | 2399294  |   LAN   |
    |   Topography   |    1     |  3   |    0    |  63   |   0   |  38400   |   IES   |
    |  Local Shades  |    1     |  4   |    0    |  64   |  62   |  65280   |   IES   |
    |  Local Shades  |    1     |  4   |   2101  |  66   |   1   |  65280   |   IES   |
    """
    # '{CATEGORY}-{TYPE}-{SUBTYPE}-{LAYER}-{COLOR}-{COLORRGB}-{KEYWORD}'
    Space = _GemType('Space', '1-001-2001-01-00-16711680-IES')
    UnconditionedSpace = _GemType('UnconditionedSpace', '1-001-2002-01-00-16711680-IES')
    TranslucentShade = _GemType('TranslucentShade', '1-001-2102-64-00-0-IES')
    ContextBuilding = _GemType('ContextBuilding', '1-002-0000-62-00-16711935-IES')
    PV = _GemType('PV', '3-202-0000-01-00-32767-PVP')
    Tree = _GemType('Tree', '1-003-0000-65-00-2399294-LAN')
    Topography = _GemType('Topography', '1-003-0000-63-00-38400-IES')
    Shade = _GemType('Shade', '1-004-0000-64-62-65280-IES')
    Shade_2 = _GemType('Shade_2', '1-004-2101-66-01-65280-IES')  # shade in VE 2023

    @classmethod
    def from_info(cls, category, type_, subtype, keyword):
        """Initialize type from GEM info."""
        if category == 1 and subtype == 2001 and type_ == 1 and keyword == 'IES':
            return cls.Space
        if category == 1 and subtype == 2002 and type_ == 1 and keyword == 'IES':
            # unconditioned space
            return cls.UnconditionedSpace
        elif category == 1 and subtype == 2102 and type_ == 1 and keyword == 'IES':
            return cls.TranslucentShade
        elif category == 1 and subtype == 0 and type_ == 2 and keyword == 'IES':
            return cls.ContextBuilding
        elif category == 3 and subtype == 0 and type_ == 202 and keyword == 'PVP':
            return cls.PV
        elif category == 1 and subtype == 0 and type_ == 3 and keyword == 'IES':
            return cls.Topography
        elif category == 1 and subtype == 0 and type_ == 3 and keyword == 'LAN':
            return cls.Tree
        elif category == 1 and subtype == 0 and type_ == 4 and keyword == 'IES':
            return cls.Shade
        elif category == 1 and subtype == 2101 and type_ == 4 and keyword == 'IES':
            return cls.Shade_2
        else:
            print(
                'Unknown combination of inputs in the input GEM file. Reach out to '
                'us with a copy of the GEM file and the information below:\n'
                '{}-{}-{}-{}'.format(category, type_, subtype, keyword)
            )
            return cls.Shade

    @classmethod
    def from_user_data(cls, user_data):
        """Get type from user_data."""
        if not user_data:
            return
        gem_type = user_data.get('__gem_type__', None)
        if not gem_type:  # support old versions of HBJSON files
            gem_type = user_data.get('__ies_type__', None)
        if gem_type == 'topography':
            return cls.Topography
        elif gem_type == 'translucent_shade':
            return cls.TranslucentShade
        elif gem_type == 'pv':
            return cls.PV
        elif gem_type == 'tree':
            return cls.Tree
