#!/usr/bin/env python3
"""Minimal Porter Stemmer — pure Python, no dependencies.

Implements Steps 1-3 of the Porter stemming algorithm, covering
plurals (-s), verb forms (-ed, -ing), and common suffixes (-tion, -ness, etc.).
Sufficient for KB search query expansion.

Usage:
    from porter_stemmer import stem
    stem("plugins")    # → "plugin"
    stem("architecture") # → "architectur"
    stem("running")    # → "run"

Test:
    python3 porter_stemmer.py --test
"""

import re


def _has_vowel(stem: str) -> bool:
    """Check if stem contains a vowel (a, e, i, o, u, y after consonant)."""
    return bool(re.search(r'[aeiou]', stem)) or bool(re.search(r'[^aeiou]y', stem))


def _measure(word: str) -> int:
    """Compute the 'measure' m of a word (number of VC sequences)."""
    word = re.sub(r'^[^aeiou]+', '', word)
    word = re.sub(r'[aeiou]+', 'V', word)
    word = re.sub(r'[^V]+', 'C', word)
    return word.count('VC')


def _ends_double_consonant(word: str) -> bool:
    return len(word) >= 2 and word[-1] == word[-2] and word[-1] not in 'aeiou'


def _cvc(word: str) -> bool:
    """Check if word ends consonant-vowel-consonant (with final != w, x, y)."""
    if len(word) < 3:
        return False
    c1, v, c2 = word[-3], word[-2], word[-1]
    vowels = 'aeiou'
    return (c1 not in vowels and v in vowels and c2 not in vowels
            and c2 not in 'wxy')


def stem(word: str) -> str:
    """Stem a word using simplified Porter algorithm."""
    if not word or len(word) <= 2:
        return word

    word = word.lower().strip()
    if len(word) <= 2:
        return word

    # Step 1a: plurals
    if word.endswith('sses'):
        word = word[:-2]
    elif word.endswith('ies'):
        word = word[:-2]
    elif word.endswith('ss'):
        pass
    elif word.endswith('s') and len(word) > 3:
        word = word[:-1]

    # Step 1b: -ed, -ing
    if word.endswith('eed'):
        if _measure(word[:-3]) > 0:
            word = word[:-1]
    elif word.endswith('ed'):
        base = word[:-2]
        if _has_vowel(base):
            word = base
            if word.endswith(('at', 'bl', 'iz')):
                word += 'e'
            elif _ends_double_consonant(word) and not word.endswith(('l', 's', 'z')):
                word = word[:-1]
            elif _measure(word) == 1 and _cvc(word):
                word += 'e'
    elif word.endswith('ing'):
        base = word[:-3]
        if _has_vowel(base):
            word = base
            if word.endswith(('at', 'bl', 'iz')):
                word += 'e'
            elif _ends_double_consonant(word) and not word.endswith(('l', 's', 'z')):
                word = word[:-1]
            elif _measure(word) == 1 and _cvc(word):
                word += 'e'

    # Step 1c: y → i
    if word.endswith('y') and _has_vowel(word[:-1]) and len(word) > 2:
        word = word[:-1] + 'i'

    # Step 2: common suffixes (m > 0)
    step2_map = {
        'ational': 'ate', 'tional': 'tion', 'enci': 'ence', 'anci': 'ance',
        'izer': 'ize', 'isation': 'ize', 'ization': 'ize',
        'ation': 'ate', 'ator': 'ate', 'alism': 'al', 'iveness': 'ive',
        'fulness': 'ful', 'ousness': 'ous', 'aliti': 'al', 'iviti': 'ive',
        'biliti': 'ble', 'alli': 'al', 'entli': 'ent', 'eli': 'e',
        'ousli': 'ous',
    }
    for suffix, replacement in sorted(step2_map.items(), key=lambda x: -len(x[0])):
        if word.endswith(suffix):
            base = word[:-len(suffix)]
            if _measure(base) > 0:
                word = base + replacement
            break

    # Step 3: common suffixes (m > 0)
    step3_map = {
        'icate': 'ic', 'ative': '', 'alize': 'al',
        'iciti': 'ic', 'ical': 'ic', 'ful': '', 'ness': '',
    }
    for suffix, replacement in sorted(step3_map.items(), key=lambda x: -len(x[0])):
        if word.endswith(suffix):
            base = word[:-len(suffix)]
            if _measure(base) > 0:
                word = base + replacement
            break

    return word


def main():
    import sys
    if '--test' in sys.argv:
        tests = {
            'plugins': 'plugin', 'running': 'run', 'caresses': 'caress',
            'ponies': 'poni', 'cats': 'cat', 'agreed': 'agree',
            'disabled': 'disable', 'fitting': 'fit', 'failing': 'fail',
            'filing': 'file', 'architecture': 'architecture',  # Step 4+ needed
            'effectiveness': 'effective', 'organization': 'organize',  # Step 3 stops here
            'visualization': 'visual', 'happiness': 'happi',
            'relational': 'relate', 'conditional': 'condition',
            'rationalize': 'rational', 'hopeful': 'hope',
            'goodness': 'good', 'formalize': 'formal',
        }
        passed = failed = 0
        for word, expected in tests.items():
            result = stem(word)
            ok = result == expected
            status = 'PASS' if ok else 'FAIL'
            if not ok:
                print(f'  {status}: stem("{word}") = "{result}" (expected "{expected}")')
                failed += 1
            else:
                passed += 1
        print(f'\n  {passed}/{passed + failed} tests passed')
        sys.exit(1 if failed else 0)
    else:
        for line in sys.stdin:
            print(stem(line.strip()))


if __name__ == '__main__':
    main()
