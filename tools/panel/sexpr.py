"""Minimal KiCad S-expression span helpers for the panel tools."""
import re

END = '# END MANAGED MARV JLCPCB DFM'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def tokens(text):
    return TOKEN.findall(text)


def children(text):
    """Direct child spans, respecting escaped strings; never reserialize geometry."""
    depth = 0
    start = None
    result = []
    for match in TOKEN.finditer(text):
        if match[0] == '(':
            if depth == 1:
                start = match.start()
            depth += 1
        elif match[0] == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('Unbalanced KiCad expression')
            if depth == 1 and start is not None:
                result.append((start, match.end()))
    if depth:
        raise ValueError('Unbalanced KiCad expression')
    return result


def locate(text, key):
    matches = [(a, b) for a, b in children(text)
               if tokens(text[a:b])[1:1 + len(key)] == list(key)]
    if len(matches) > 1:
        raise ValueError(f'Duplicate KiCad setting: {key}')
    return matches[0] if matches else None


def node(text, *key):
    span = locate(text, key)
    if span is None:
        raise ValueError(f'Missing KiCad setting: {key}')
    return text[slice(*span)]


def replace_node(text, key, replacement, indent='\t\t'):
    span = locate(text, key)
    if span is not None:
        old = text[slice(*span)]
        if tokens(old) == tokens(replacement):
            return text  # preserve existing formatting and mtime on no-op
        return text[:span[0]] + replacement + text[span[1]:]
    end = text.rfind(')')
    return text[:end].rstrip() + '\n' + indent + replacement + '\n' + text[end:]


