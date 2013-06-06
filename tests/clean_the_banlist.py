#!/usr/bin/env python

"""Clean a banlist that contains OCR errors. We originally tried to strip leading
prefixes such as http://web.archive.org/web/timestamp/ from the urls, but our list
of patterns grew too large, so now we use urlparse.

Here is the incomplete list of regexes for stripping prefixes, which is no longer used:
    patterns = [r'^http://web.archive.org/web/(?:\d|S){14}/', #catch ocr errors like 2003020S115930 with an "S"
                r'^http://web.archive.org/web/\*/',
                r'^htlp://web.archive.org/web/\*/',
                r'^http://replay.waybackmachine.org/\*/',
                r'^http://classic-web.archive.org/web/\d{14}/',
                r'^http://classic-web.archive.org/web/\d{14}/',
                r'^classic-web.archive.org/web/\d{14}/',
                r'^htlp://web.archive.bibalex.org/web/\d{14}/',
                r'^htrp://classic-web.archive.org/web/\d{14}/',
                r'^htrp://web.archive.bibalex.org/web/\d{14}/',
                r'^htlp://replay.waybackmachine.org/\d{14}/',
                r'^http://crawls-wm.us.archive.org/2bc/\*/',
                r'^http://crawls-wm.us.archive.org/2bc/\d{14}/',
                r'^http://replay.web.archive.org/\d{14}/',
                r'^http://wayback.archive.org/web/\*/',
                r'^http://web.archive.bibalex.ong/web/\d{14}/',
                r'^http://web.archive.bibalex.org/\d{14}/',
                r'^http://web.archive.bibalex.org/web/\*/',
                r'^http://web.archive.bibalex.org/web/\*hh_/',
                r'^http://web.archive.bibalex.org/web/\*sa_/',
                r'^http://web.archive.bibalex.org/web/\d{12,14}/?', #handle short timecode and missing trailing slash
                r'^http://web.archive.bibalex.org/web/20020831045708lhttp://',
                r'^http://replay.waybackmachine.org/(?:\d|B|O){13,14}/', # catch OCR errors like 2003060BOB5B29 with a "B" and short ones like 2003203161650
                r'^http://replay.waybackmachine.org/\d{14}im_/',
                r'^http://replay.waybackmachine.org/200412070711221http://',
                r'^http://web.archive.bibalex.orgAveb/\d{14}/',
                r'^http://web.archive.bibalex.orgyweb/\d{14}/',
                ]
"""

import sys
import re
import urlparse

comment = None


def get_prefix(url_list, url):
    for prefix in url_list:
        if url.startswith(prefix):
            return prefix

    return None


def remove_prefix(s):
    orig_s = s

    #fix OCR errors
    s = s.replace('htlp://', 'http://')
    s = s.replace('htrp://', 'http://')
    s = s.replace('hHp://',  'http://')
    s = s.replace('http:/web', 'http://web')
    s = s.replace('/vvww.', '/www.')
    s = s.replace('/wvvw.', '/www.')
    s = s.replace('/wvw.',  '/www.')
    s = s.replace('/wvwv.', '/www.')
    s = s.replace('/wwvv.', '/www.')
    s = s.replace('bibatex.org', 'bibalex.org')
    s = s.replace('.ong/', '.org/')

    #prevent urlparse errors
    if not re.match(r'^https?://', s):
        s = 'http://'+s

    result = urlparse.urlparse(s)
    if not (('archive.org' in result.netloc) or ('bibalex.org' in result.netloc) or ('waybackmachine.org' in result.netloc)):
        print 'unable to parse url:', s, orig_s
        sys.exit(-1)

    start_pos = result.path.find('http://')
    if start_pos == -1:
        match = None
        patterns = [r'^/web/\d{14}/(.+)$',
                    r'^/web/\*/(.+)$',
                    r'^/\*/(.+)$',
                    r'^/\d{14}(?:im_)?/(.+)$',
                    r'^/web/\*hh_/(.+)$',
                   ]

        for p in patterns:
            match = re.match(p, result.path, flags=re.I)
            if match:
                break

        if match:
            s = match.group(1)
        else:
            print 'unable to find match for url:', s
            sys.exit(-1)
    else:
        s = result.path[start_pos:]

    return s


file = sys.argv[1]
f = open(file)

url_set = set()
for line in f:
    #print 'processing', line

    url = remove_prefix(line.strip())
    url = url.decode('utf-8')
    url = url.rstrip(u'\u2028')
    if not re.match(r'^https?://', url):
        url = 'http://' + url

    url_set.add(url)


#remove prefix matches
urls_by_length = sorted(url_set, key=len) #shortest first
urls = []
while urls_by_length:
    url = urls_by_length.pop() #get last (longest) element
    prefix = get_prefix(urls_by_length, url)
    if prefix is None:
        urls.append(url)

urls.sort()

for url in urls:
    if ('archive.org' in url) or ('bibalex.org' in url) or ('waybackmachine.org' in url):
        print 'unfiltered url:', url
        sys.exit(-1)

    if comment:
        url += ' #'+comment

    try:
        print url.encode('ascii')
    except:
        print 'UnicodeError', 'BAD URL: '+repr(url)
        print 'terminating'
        sys.exit(-1)
