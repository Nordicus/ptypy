# -*- coding: utf-8 -*-
"""\
Parameter validation. This module parses the file
``resources/parameters_descriptions.csv`` to extract the parameter
defaults for |ptypy|. It saves all parameters in the form of 
a :py:class:`PDesc` object, which are flat listed in 
`parameter_descriptions` or in `entry_points_dct`, which only contains
parameters with subparameters (children).

This file is part of the PTYPY package.

    :copyright: Copyright 2014 by the PTYPY team, see AUTHORS.
    :license: GPLv2, see LICENSE for details.
"""

import ast
import weakref
from collections import OrderedDict

if __name__=='__main__':
    from ptypy.utils.parameters import Param
else:
    from .parameters import Param

__all__= ['create_default_template','make_sub_default','validate',\
          'entry_points_dct', 'parameter_descriptions', 'PDesc']

#! Validator message codes
CODES = Param(
    PASS=1,
    FAIL=0,
    UNKNOWN=2,
    MISSING=3,
    INVALID=4)

#! Inverse message codes
CODE_LABEL = dict((v, k) for k, v in CODES.items())

"""
# Populate the dictionary of all entry points.

# All ptypy parameters in an ordered dictionary as (entry_point, PDesc) pairs.
parameter_descriptions = OrderedDict()
del OrderedDict

# All parameter containers in a dictionary as (entry_point, PDesc) pairs.
# Subset of :py:data:`parameter_descriptions`
entry_points_dct = {}
"""

# Logging levels
import logging

_logging_levels = Param(
    PASS=logging.INFO,
    FAIL=logging.CRITICAL,
    UNKNOWN=logging.WARN,
    MISSING=logging.WARN,
    INVALID=logging.ERROR)

del logging


class Parameter(object):
    """
    Base class for parameter descriptions and validation. This class is used to hold both command line arguments
    and Param-type parameter descriptions.
    """

    def __init__(self, name, parent=None, separator='.', info=None):
                
        #: Name of parameter
        self.name = name
        
        #: Parent parameter (:py:class:`Parameter` type) if it has one.
        self.parent = parent
        
        self.descendants = {}
        """ Flat list of all sub-Parameters. These are weak references
        if not root."""
        
        if self._is_child:
            import weakref
            self.descendants = weakref.WeakValueDictionary()

        #: Hierarchical tree of sub-Parameters.
        self.children = {}
        
        self.separator = separator
        
        # Required and optional attributes
        self.required = []
        self.optional = []
        self.info = OrderedDict()
        self._parse_info(info)

        self.num_id = 0
        self.options = dict.fromkeys(self.required, '')
        self._all_options = {}
        
    @property
    def descendants_options(self):
        return self._all_options.keys()
        
    @property
    def _is_child(self):
        """
        Type check
        """
        return type(self.parent) is self.__class__

    def _parse_info(self,info=None):
        if info is not None:
            self.info.update(info)
            
            r = []
            o = []
        
            for option,text in self.info.items():
                if 'required' in text or 'mandatory' in text:
                    r += [option]
                else:
                    o += [option]
            self.required = r
            self.optional = o

    def _new(self, name=None):
        """
        Create a new child of this object with same info dict. If name is None, a
        default is used.
        """
        n = name if name is not None and str(name) == name else 'ch%02d' % len(self.descendants)
        return self.__class__(name=n, parent=self, separator=self.separator, info=self.info)
        
    def _name_descendants(self, separator=None):
        """
        Transform the flat list of descendants into tree hierarchy, stored in self.children.
        Create roots if parameter has a dangling root.
        """
        sep = separator if separator is not None else self.separator

        for name, desc in self.descendants.items():
            if sep not in name:
                # "leaf" object
                desc.name = name
                self.children[name] = desc
            else:
                # "node" object.
                names = name.split(sep)
                
                # Extract parent name
                nm = names[0]
                
                # Create parent if non-existent
                p = self.descendants.get(nm)
                if p is None:
                    # Found dangling parameter. Create a root
                    p = self._new(name=nm)
                    self._new_desc(nm, p)
                    self.children[nm] = p
                    
                # transfer ownership
                p.descendants[sep.join(names[1:])] = desc
                desc.parent = p
        
        # recursion
        for desc in self.children.values():
            desc._name_descendants()
            
    def _get_root(self):
        """
        Return root of parameter tree.
        """
        if self.parent is None:
            return self
        else:
            return self.parent.root

    def _store_options(self, dct):
        """
        Read and store options and check that the minimum selections
        of options is present.
        """
        
        if self.required is not None and type(self.required) is list:
            missing = [r for r in self.required if r not in dct.keys()]
            if missing:
                raise ValueError('Missing required option(s) <%s> for parameter %s.' % (', '.join(missing), self.name))

        self.options = dict.fromkeys(self.required)
        self.options.update(dct)
        
    @property    
    def root(self):
        return self._get_root()
            
    @property
    def path(self):
        if self.parent is None:
            return self.name
        else:
            return self.parent.path + self.separator + self.name
            
    def _new_desc(self, name, desc, update_in_parent=True):
        """
        Update the new entry to the root.
        """
        self.descendants[name] = desc
        
        # add all options to parent class
        self._all_options.update(desc.options)
        
        if update_in_parent:
            if self._is_child:
                # You are not the root
                self.parent._new_desc(self.name+self.separator+name, desc)
            else:
                # You are the root. Do root things here.
                pass
                
    def load_csv(self, fbuffer, **kwargs):
        """
        Load from csv as a fielded array. Keyword arguments are passed
        on to csv.DictReader
        """
        from csv import DictReader
        CD = DictReader(fbuffer, **kwargs)
        
        if 'level' in CD.fieldnames:
            chain = []
            
            # old style CSV, name + level sets the path
            for num, dct in enumerate(list(CD)):
            
                # Get parameter name and level in the hierarchy
                level = int(dct.pop('level'))
                name = dct.pop('name')
            
                # translations
                dct['help'] = dct.pop('shortdoc')
                dct['doc'] = dct.pop('longdoc')
                if dct.pop('static').lower() != 'yes':
                    continue
            
                desc = self._new(name)
                desc._store_options(dct)
                desc.num_id = num
                
                if level == 0:  
                    chain = [name]
                else:
                    chain = chain[:level]+[name]
            
                self._new_desc(self.separator.join(chain), desc)
        else:
            # new style csv, name and path are synonymous
            for dct in list(CD):
                name = dct['path']
                desc = self._new(name)
                desc._store_options(dct)
                self._new_desc(name, desc)
        
        self._name_descendants()
        
    def save_csv(self, fbuffer, **kwargs):
        """
        Save to fbuffer. Keyword arguments are passed
        on to csv.DictWriter
        """
        from csv import DictWriter
        
        fieldnames = self.required + self.optional
        fieldnames += [k for k in self._all_options.keys() if k not in fieldnames]
        
        DW = DictWriter(fbuffer, ['path'] + fieldnames)
        DW.writeheader()
        for key in sorted(self.descendants.keys()):
            dct = {'path':key}
            dct.update(self.descendants[key].options)
            DW.writerow(dct)
        
    def load_json(self, fbuffer):
        
        raise NotImplementedError
    
    def save_json(self, fbuffer):
        
        raise NotImplementedError

    def load_conf_parser(self, fbuffer, **kwargs):
        """
        Load Parameter defaults using Python's ConfigParser
        
        Each parameter occupies its own section.
        Separator characters in sections names map to a tree-hierarchy.
        
        Keyword arguments are forwarded to `ConfigParser.RawConfigParser`
        """
        from ConfigParser import RawConfigParser as Parser
        parser = Parser(**kwargs)
        parser.readfp(fbuffer)
        for num, sec in enumerate(parser.sections()):
            desc = self._new(name=sec)
            desc._store_options(dict(parser.items(sec)))
            self._new_desc(sec, desc)
        
        self._name_descendants()
        return parser
            
    def save_conf_parser(self, fbuffer, print_optional=True):
        """
        Save Parameter defaults using Pythons ConfigParser
        
        Each parameter occupies its own section. 
        Separator characters in sections names map to a tree-hierarchy.
        """
        from ConfigParser import RawConfigParser as Parser
        parser = Parser()
        dct = self.descendants
        for name in sorted(dct.keys()):
            if dct[name] is None:
                continue
            else:
                parser.add_section(name)
                for k, v in self.descendants[name].options.items():
                    if (v or print_optional) or (k in self.required):
                        parser.set(name, k, v)
        
        parser.write(fbuffer)
        return parser
        
    def make_doc_rst(self, prst, use_root=True):
        """
        Pretty-print in RST format the whole structure.
        """
        Header = '.. _parameters:\n\n'
        Header += '************************\n'
        Header += 'Parameter tree structure\n'
        Header += '************************\n\n'
        prst.write(Header)
        
        root = self.get_root()  # if use_root else self
        shortdoc = 'shortdoc'
        longdoc = 'longdoc'
        default = 'default'
        lowlim = 'lowlim'
        uplim = 'uplim'
        
        start = self.get_root()
        
        for name, desc in root.descendants.iteritems():
            if name == '':
                continue
            if hasattr(desc, 'children') and desc.parent is root:
                prst.write('\n'+name+'\n')
                prst.write('='*len(name)+'\n\n')
            if hasattr(desc, 'children') and desc.parent.parent is root:
                prst.write('\n'+name+'\n')
                prst.write('-'*len(name)+'\n\n')
            
            opt = desc.options

            prst.write('.. py:data:: '+name)
            # prst.write('('+', '.join([t for t in opt['type']])+')')
            prst.write('('+opt['type']+')')
            prst.write('\n\n')
            num = str(opt.get('ID'))
            prst.write('   *('+num+')* '+opt[shortdoc]+'\n\n')
            prst.write('   '+opt[longdoc].replace('\n', '\n   ')+'\n\n')
            prst.write('   *default* = ``'+str(opt[default]))
            if opt[lowlim] is not None and opt[uplim] is not None:
                prst.write(' (>'+str(opt[lowlim])+', <'+str(opt[uplim])+')``\n')
            elif opt[lowlim] is not None and opt[uplim] is None:
                prst.write(' (>'+str(opt[lowlim])+')``\n')
            elif opt[lowlim] is None and opt[uplim] is not None:
                prst.write(' (<'+str(opt[uplim])+')``\n')
            else:
                prst.write('``\n')
                
            prst.write('\n')
        prst.close()


class ArgParseParameter(Parameter):
    DEFAULTS = OrderedDict([
        ('default', 'Default value for parameter.'),
        ('help', 'A small docstring for command line parsing (required).'),
        ('choices', 'If parameter is list of choices, these are listed here.')
    ])

    def __init__(self, *args, **kwargs):
        
        info = self.DEFAULTS.copy()
        ninfo = kwargs.get('info')
        if ninfo is not None:
            info.update(ninfo)
            
        kwargs['info'] = info
        
        super(ArgParseParameter, self).__init__(*args,**kwargs)

    @property
    def help(self):
        """
        Short descriptive explanation of parameter
        """
        return self.options.get('help', '')

    @property
    def default(self):
        """
        Returns default as a Python type
        """
        default = str(self.options.get('default', ''))
        
        if not default:
            return None
        else:
            return self.eval(default)

    def eval(self, val):
        """
        A more verbose wrapper around `ast.literal_eval`
        """
        try:
            return ast.literal_eval(val)
        except ValueError as e:
            msg = e.message+". could not read %s for parameter %s" % (val, self.name)
            raise ValueError(msg)
            
    @property
    def choices(self):
        """
        If parameter is a list of choices, these are listed here.
        """
        # choices is an evaluable list
        c = self.options.get('choices', '')
        if str(c) == '':
            c = None
        else:
            try:
                c = ast.literal_eval(c.strip())
            except SyntaxError('Evaluating `choices` %s for parameter %s failed' % (str(c), self.name)):
                c = None
        
        return c

    def make_default(self, depth=1):
        """
        Creates a default parameter structure, from the loaded parameter
        descriptions in this module
        
        Parameters
        ----------            
        depth : int
            The depth in the structure to which all sub nodes are expanded
            All nodes beyond depth will be returned as empty dictionaries
            
        Returns
        -------
        pars : dict
            A parameter branch as nested dicts.
        
        Examples
        --------
        >>> from ptypy import parameter
        >>> print parameter.children['io'].make_default()
        """
        out = {}
        if depth <= 0:
            return out
        for name, child in self.children.iteritems():
            if child.children and child.default is None:
                out[name] = child.make_default(depth=depth-1)
            else:
                out[name] = child.default
        return out
        
    def _get_type_argparse(self):
        """
        Returns type or callable that the argparser uses for 
        reading in cmd line argements.
        """
        return type(self.default)
        
    def add2argparser(self, parser=None, prefix='', excludes=('scans', 'engines'), mode='add'):
        """
        Add parameter to an argparse.ArgumentParser instance (or create and return one if parser is None)
        prefix is
        """

        sep = self.separator
        pd = self
        argsep = '-'

        if parser is None:
            from argparse import ArgumentParser
            description = """
            Parser for %s
            Doc: %s
            """ % (pd.name, pd.help)
            parser = ArgumentParser(description=description)
        
        # overload the parser
        if not hasattr(parser, '_aux_translator'):
            parser._aux_translator = {}

        # get list of descendants and remove separator
        ndesc = dict((k.replace(sep, argsep), v) for k, v in self.descendants.items())

        groups = {}
        
        for name, pd in ndesc.items():
            if pd.name in excludes:
                continue
            if pd.children:
                groups[name] = parser.add_argument_group(title=prefix+name, description=pd.help)

        for name, pd in ndesc.iteritems():
            
            if pd.name in excludes:
                continue
            up = argsep.join(name.split(argsep)[:-1])
            # recursive part
            parse = groups.get(up, parser)

            """
            # this should be part of PDesc I guess.
            typ = type(pd.default)
            
            for t in pd.type:
                try:
                    typ= eval(t)
                except BaseException:
                    continue
                if typ is not None:
                    break

            if typ is None:
                u.verbose.logger.debug('Failed evaluate type strings %s of parameter %s in python' % (str(pd.type),name))
                return parser
                
            if type(typ) is not type:
                u.verbose.logger.debug('Type %s of parameter %s is not python type' % (str(typ),name))
                return parser
            """
            typ = pd._get_type_argparse()
            
            if typ is bool:
                # Command line switches have no arguments, so treated differently
                flag = '--no-'+name if pd.value else '--'+name
                action = 'store_false' if pd.value else 'store_true'
                parse.add_argument(flag, dest=name, action=action, help=pd.shortdoc)
            else:
                d = pd.default
                defstr = d.replace('%(', '%%(') if str(d) == d else str(d)
                parse.add_argument('--'+name, dest=name, type=typ, default=pd.default, choices=pd.choices,
                                   help=pd.help + ' (default=%s)' % defstr)
        
            parser._aux_translator[name] = pd
            
        return parser

        
class EvalParameter(ArgParseParameter):
    """
    Parameter class to store metadata for all ptypy parameters (default, limits, documentation, etc.)
    """
    _typemap = {'int': 'int',
                'float': 'float',
                'complex': 'complex',
                'str': 'str',
                'bool': 'bool',
                'tuple': 'tuple',
                'list': 'list',
                'array': 'ndarray',
                'Param': 'Param',
                'None': 'NoneType',
                'file': 'str',
                '': 'NoneType'}

    _evaltypes = ['int', 'float', 'tuple', 'list', 'complex']
    _copytypes = ['str', 'file']
    
    DEFAULTS = OrderedDict([
        ('default', 'Default value for parameter (required).'),
        ('help', 'A small docstring for command line parsing (required).'),
        ('doc', 'A longer explanation for the online docs.'),
        ('type', 'Comma separated list of acceptable types.'),
        ('userlevel', """User level, a higher level means a parameter that is 
                     less likely to vary or harder to understand."""),
        ('choices', 'If parameter is list of choices, these are listed here.'),
        ('uplim', 'Upper limit for scalar / integer values'),
        ('lowlim', 'Lower limit for scalar / integer values'),
    ])
     
    def __init__(self, *args, **kwargs):

        # self.DEFAULT is the only valid "info" to provide to the superclass.
        kwargs['info'] = self.DEFAULTS.copy()
        super(EvalParameter, self).__init__(*args, **kwargs)
        
    @property
    def default(self):
        """
        Default value as a Python type
        """
        default = str(self.options.get('default', ''))
        
        # this destroys empty strings
        default = default if default else None
        
        if default is None:
            out = None
        # should be only strings now
        elif default.lower() == 'none':
            out = None
        elif default.lower() == 'true':
            out = True
        elif default.lower() == 'false':
            out = False
        elif self.is_evaluable:
            out = ast.literal_eval(default)
        else:
            out = default
        
        return out 
        
    @property
    def type(self):
        """
        List of possible data types.
        """
        types = self.options.get('type', None)
        tm = self._typemap
        if types is not None:
            types = [tm[x.strip()] if x.strip() in tm else x.strip() for x in types.split(',')]
        
        return types        
       
    @property
    def limits(self):
        """
        (lower, upper) limits if applicable. (None, None) otherwise
        """
        if self.type is None:
            return None, None
            
        ll = self.options.get('lowlim', None)
        ul = self.options.get('uplim', None)
        if 'int' in self.type:
            lowlim = int(ll) if ll else None
            uplim = int(ul) if ul else None
        else:
            lowlim = float(ll) if ll else None
            uplim = float(ul) if ul else None
            
        return lowlim, uplim
        
    @property
    def doc(self):
        """
        Long documentation, may contain *sphinx* inline markup.
        """
        return self.options.get('doc', '')

    @property
    def userlevel(self):
        """
        User level, a higher level means a parameter that is less 
        likely to vary or harder to understand.
        """
        # User level (for gui stuff) is an int
        ul = self.options.get('userlevel', 1)
        
        return int(ul) if ul else None
     
    @property
    def is_evaluable(self):
        for t in self.type:
            if t in self._evaltypes:
                return True
                break
        return False

    def check(self, pars, walk):
        """
        Check that input parameter pars is consistent with parameter description.
        If walk is True and pars is a Param object, checks are also conducted for all
        sub-parameters.

        Returns a dictionary report using CODES values.
        """
        ep = self.path
        out = {}
        val = {}

        # 1. Data type
        if self.type is None:
            # Unconclusive
            val['type'] = CODES.UNKNOWN
            val['lowlim'] = CODES.UNKNOWN
            val['uplim'] = CODES.UNKNOWN
            return {ep: val}
        else:
            val['type'] = CODES.PASS if (type(pars).__name__ in self.type) else CODES.FAIL

        # 2. limits
        lowlim, uplim = self.limits
        
        if lowlim is None:
            val['lowlim'] = CODES.UNKNOWN
        else:
            val['lowlim'] = CODES.PASS if (pars >= self.lowlim) else CODES.FAIL
        if uplim is None:
            val['uplim'] = CODES.UNKNOWN
        else:
            val['uplim'] = CODES.PASS if (pars <= self.uplim) else CODES.FAIL

        # 3. Extra work for parameter entries
        if 'Param' in self.type:
            # Check for missing entries
            for k, v in self.children.items():
                if k not in pars:
                    val[k] = CODES.MISSING

            # Check for excess entries
            for k, v in pars.items():
                if k not in self.children:
                    val[k] = CODES.INVALID
                elif walk:
                    # Validate child
                    out.update(self.children[k].check(v, walk))

        out[ep] = val
        return out
        
    def validate(self, pars, walk=True, raisecodes=[CODES.FAIL, CODES.INVALID]):
        """
        Check that the parameter structure `pars` matches the documented 
        constraints for this node / parameter.
    
        The function raises a RuntimeError if one of the code in the list 
        `raisecodes` has been found. If raisecode is empty, the function will 
        always return successfully but problems will be logged using logger.
    
        Parameters
        ----------
        pars : Param
            A parameter set to validate
        
        walk : bool
            If ``True`` (*default*), navigate sub-parameters.
        
        raisecodes: list
            List of codes that will raise a RuntimeError.
        """
        from ptypy.utils.verbose import logger
        
        d = self.check(pars, walk=walk)
        do_raise = False
        for ep, v in d.items():
            for tocheck, outcome in v.items():
                logger.log(_logging_levels[CODE_LABEL[outcome]], '%-50s %-20s %7s' % (ep, tocheck, CODE_LABEL[outcome]))
                do_raise |= (outcome in raisecodes)
        if do_raise:
            raise RuntimeError('Parameter validation failed.')
            
    def sanity_check(self, depth=10):
        """
        Checks if default parameters from configuration are 
        self-constistent with limits and choices.
        """
        self.validate(self.make_default(depth=depth))


def create_default_template(filename=None, user_level=0, doc_level=2):
    """
    Creates a (descriptive) template for ptypy.
    
    Parameters
    ----------
    filename : str
        python file (.py) to generate, will be overriden if it exists
    
    user_level : int
        Filter parameters to display on those with less/equal user level
    
    doc_level : int
        - if ``0``, no comments. 
        - if ``1``, *short_doc* as comment in script
        - if ``>2``, *long_doc* and *short_doc* as comment in script
    """
    def _format_longdoc(doc):
        ld = doc.strip().split('\n')
        out = []
        for line in ld:
            if len(line)==0:
                continue
            if len(line)>75:
                words = line.split(' ')
                nline = ''
                count = 0
                for word in words:
                    nline+=word+' '
                    count+=len(word)
                    if count > 70:
                        count = 0
                        out.append(nline[:-1])
                        nline=""
                out.append(nline[:-1])
            else:
                out.append(line)
        if out:
            return '# '+'\n# '.join(out)+'\n' 
        else:
            return ''
            
    if filename is None:
        f = open('ptypy_template.py','w')
    else:
        f = open(filename,'w')
    h = '"""\nThis Script was autogenerated using\n'
    h+= '``u.create_default_template("%s",%d,%d)``\n' %(str(filename),user_level,doc_level)
    h+= 'It is only a TEMPLATE and not a working reconstruction script.\n"""\n\n'
    h+= "import numpy as np\n"
    h+= "import ptypy\n"
    h+= "from ptypy.core import Ptycho\n"
    h+= "from ptypy import utils as u\n\n"
    try:
        from ptypy.utils.verbose import headerline
        h+= headerline('Ptypy Parameter Tree','l','#')+'\n'
    except ImportError:
        h+= '### Ptypy Parameter Tree ###\n\n'
    #h+= "p = u.Param()\n"
    f.write(h)
    for entry, pd in parameter_descriptions.iteritems():
        if user_level < pd.userlevel:
            continue
        if pd.children is not None:
            value = "u.Param()"
        else:
            val = pd.value
            if str(val)== val :
                value = '"%s"' % str(val)
            else:
                value = str(val)
        ID ="%02d" % pd.ID if hasattr(pd,'ID') else 'NA'
        if doc_level > 0:
            f.write('\n'+"## (%s) " % ID +pd.shortdoc.strip()+'\n')
        if doc_level > 1:
            f.write(_format_longdoc(pd.longdoc))
        f.write('p'+entry+ ' = ' + value+'\n')
        
    f.write('\n\nPtycho(p,level=5)\n')
    f.close()


    
if __name__ =='__main__':
    from ptypy import utils as u
    
    
    
    parser = _add2argparser(entry_point='.scan.illumination')
    parser.parse_args()
    
