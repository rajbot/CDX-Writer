#!/usr/bin/env python

""" This script requires a modified version of Hanzo Archives' warc-tools:
http://code.hanzoarchives.com/warc-tools/src/tip/hanzo/warctools

This script is loosely based on warcindex.py:
http://code.hanzoarchives.com/warc-tools/src/1897e2bc9d29/warcindex.py

The functions that start with "get_" (as opposed to "parse_") are called by the
dispatch loop in make_cdx using getattr().
"""
from warctools import ArchiveRecord #from https://bitbucket.org/rajbot/warc-tools
from surt      import surt          #from https://github.com/rajbot/surt

import os
import re
import sys
import base64
import chardet
import hashlib
import urllib
import urlparse
from datetime  import datetime
from optparse  import OptionParser


class CDX_Writer(object):

    #___________________________________________________________________________
    def __init__(self, file, format, use_full_path=False, file_prefix=None, all_records=False):

        self.field_map = {'M': 'AIF meta tags',
                          'N': 'massaged url',
                          'S': 'compressed record size',
                          'V': 'compressed arc file offset',
                          'a': 'original url',
                          'b': 'date',
                          'g': 'file name',
                          'k': 'new style checksum',
                          'm': 'mime type',
                          'r': 'redirect',
                          's': 'response code',
                         }

        self.file   = file
        self.format = format
        self.all_records  = all_records
        self.crlf_pattern = re.compile('\r?\n\r?\n')

        #similar to what what the wayback uses:
        self.fake_build_version = "archive-commons.0.0.1-SNAPSHOT-20120112102659-python"

        #these fields are set for each record in the warc
        self.offset        = 0
        self.mime_type     = None
        self.headers       = None
        self.content       = None
        self.meta_tags     = None
        self.response_code = None

        #Large html files cause lxml to segfault
        #problematic file was 154MB, we'll stop at 5MB
        self.lxml_parse_limit = 5 * 1024 * 1024

        if use_full_path:
            self.warc_path = os.path.abspath(file)
        elif file_prefix:
            self.warc_path = os.path.join(file_prefix, file)
        else:
            self.warc_path = file

    # parse_http_header()
    #___________________________________________________________________________
    def parse_http_header(self, header_name):
        if self.headers is None:
            return None

        pattern = re.compile(header_name+':\s*(.+)', re.I)
        for line in iter(self.headers):
            m = pattern.match(line)
            if m:
                return m.group(1)
        return None

    # parse_http_content_type_header()
    #___________________________________________________________________________
    def parse_http_content_type_header(self, record):
        content_type = self.parse_http_header('content-type')
        if content_type is None:
            return 'unk'

        # some http responses end abruptly: ...Content-Length: 0\r\nConnection: close\r\nContent-Type: \r\n\r\n\r\n\r\n'
        content_type = content_type.strip()
        if '' == content_type:
            return 'unk'

        m = re.match('(.+?);', content_type)
        if m:
            content_type = m.group(1)

        if re.match('^[a-z0-9\-\.\+/]+$', content_type):
            return content_type
        else:
            return 'unk'


    # parse_charset()
    #___________________________________________________________________________
    def parse_charset(self):
        charset = None
        charset_pattern = re.compile('charset\s*=\s*([a-z0-9_\-]+)', re.I)

        content_type = self.parse_http_header('content-type')
        if content_type:
            m = charset_pattern.search(content_type)
            if m:
                charset = m.group(1)


        if charset is None and self.meta_tags is not None:
            content_type = self.meta_tags.get('content-type')
            if content_type:
                m = charset_pattern.search(content_type)
                if m:
                    charset = m.group(1)

        if charset:
            charset = charset.replace('win-', 'windows-')

        return charset

    # parse_meta_tags
    #___________________________________________________________________________
    def parse_meta_tags(self, record):
        """We want to parse meta tags in <head>, even if not direct children.
        e.g. <head><noscript><meta .../></noscript></head>

        What should we do about multiple meta tags with the same name?
        currently, we append the content attribs together with a comma seperator.

        We use either the 'name' or 'http-equiv' attrib as the meta_tag dict key.
        """

        if not ('response' == record.type and 'text/html' == self.mime_type):
            return None

        if self.content is None:
            return None

        meta_tags = {}

        #lxml.html can't parse blank documents
        html_str = self.content.strip()
        if '' == html_str:
            return meta_tags

        #lxml can't handle large documents
        if record.content_length > self.lxml_parse_limit:
            return meta_tags

        # lxml was working great with ubuntu 10.04 / python 2.6
        # On ubuntu 11.10 / python 2.7, lxml exhausts memory hits the ulimit
        # on the same warc files. Unfortunately, we don't ship a virtualenv,
        # so we're going to give up on lxml and use regexes to parse html :(

        meta_tags = {}
        #we only want to look for meta tags that occur before the </head> tag
        head_limit = None
        m = re.search('(</head>)', html_str, re.I)
        if m:
            head_limit = m.start(1)

        for x in re.finditer("(<meta[^>]+?>)", html_str, re.I):
            if head_limit is not None and x.start(1) >= head_limit:
                break

            name = None
            content = None
            m = re.match('''<meta\s+.*(?:name|http-equiv)\s*=\s*(['"]?)(.*?)(['"]?)\s+content\s*=\s*(['"]?)(.*?)(['"]?)\s*/?>$''', x.group(1), re.I)
            if m:
                name = m.group(2).lower()
                content = m.group(5)
            else:
                m = re.match('''<meta\s+.*content\s*=\s*(['"]?)(.*?)(['"]?)\s+(?:name|http-equiv)\s*=\s*(['"]?)(.*?)(['"]?)\s*/?>$''', x.group(1), re.I)
                if m:
                    name = m.group(5).lower()
                    content = m.group(2)
                else:
                    continue

            if name not in meta_tags:
                meta_tags[name] = content
            else:
                if 'refresh' != name:
                    #for redirect urls, we only want the first refresh tag
                    meta_tags[name] += ',' + content

        return meta_tags


    # get_AIF_meta_tags() //field "M"
    #___________________________________________________________________________
    def get_AIF_meta_tags(self, record):
        """robot metatags, if present, should be in this order: A, F, I
        """
        x_robots_tag = self.parse_http_header('x-robots-tag')

        if x_robots_tag is None:
            if not self.meta_tags:
                return '-'
            if 'robots' not in self.meta_tags:
                return '-'

        robot_tags = []
        if self.meta_tags and 'robots' in self.meta_tags:
            robot_tags += self.meta_tags['robots'].split(',')
        if x_robots_tag:
            robot_tags += x_robots_tag.split(',')
        robot_tags = [x.strip().lower() for x in robot_tags]

        s = ''
        if 'noarchive' in robot_tags:
            s += 'A'
        if 'nofollow' in robot_tags:
            s += 'F'
        if 'noindex' in robot_tags:
            s += 'I'

        if s:
            return ''.join(s)
        else:
            return '-'


    # get_massaged_url() //field "N"
    #___________________________________________________________________________
    def get_massaged_url(self, record):
        if 'warcinfo' == record.type:
            return self.get_original_url(record)
        else:
            try:
                return surt(record.url)
            except ValueError:
                return self.get_original_url(record)


    # get_compressed_record_size() //field "S"
    #___________________________________________________________________________
    def get_compressed_record_size(self, record):
        return str(record.compressed_record_size)

    # get_compressed_arc_file_offset() //field "V"
    #___________________________________________________________________________
    def get_compressed_arc_file_offset(self, record):
        return str(self.offset)

    # get_original_url() //field "a"
    #___________________________________________________________________________
    def get_original_url(self, record):
        if 'warcinfo' == record.type:
            url = 'warcinfo:/%s/%s' % (self.file, self.fake_build_version)
            return url

        url = record.url

        # There are few arc files from 2002 that have non-ascii characters in
        # the url field. These are not utf-8 characters, and the charset of the
        # page might not be specified, so use chardet to try and make these usable.
        if isinstance(url, str):
            try:
                url.decode('ascii')
            except UnicodeDecodeError:
                enc = chardet.detect(url)
                if enc and enc['encoding']:
                    if 'EUC-TW' == enc['encoding']:
                        # We don't have the EUC-TW encoding installed, and most likely
                        # something is so wrong that we probably can't recover this url
                        url = url.decode('Big5', 'replace')
                    else:
                        url = url.decode(enc['encoding'], 'replace')
                else:
                    url = url.decode('utf-8', 'replace')

        # Some arc headers contain urls with the '\r' character, which will cause
        # problems downstream when trying to process this url, so escape it.
        # While we are at it, replace other newline chars.
        url = url.replace('\r', '%0D')
        url = url.replace('\n', '%0A')
        url = url.replace('\x0c', '%0C') #formfeed

        return url

    # get_date() //field "b"
    #___________________________________________________________________________
    def get_date(self, record):
        #warcs and arcs use a different date format
        #consider using dateutil.parser instead

        if 14 == len(record.date):
            #arc record already has date in the format we need
            return record.date
        elif 16 == len(record.date):
            #some arc records have 16-digit dates: 2000082305410049
            return record.date[:14]
        elif 12 == len(record.date):
            #some arc records have 12-digit dates: 200011201434
            return record.date + '00'

        #warc record
        date = datetime.strptime(record.date, "%Y-%m-%dT%H:%M:%SZ")
        return date.strftime("%Y%m%d%H%M%S")

    # get_file_name() //field "g"
    #___________________________________________________________________________
    def get_file_name(self, record):
        return self.warc_path

    # get_new_style_checksum() //field "k"
    #___________________________________________________________________________
    def get_new_style_checksum(self, record):
        """Return a base32-encoded sha1
        For revisit records, return the original sha1
        """

        if 'revisit' == record.type:
            digest = record.get_header('WARC-Payload-Digest')
            if digest is None:
                return '-'
            else:
                return digest.replace('sha1:', '')
        elif 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            digest = record.get_header('WARC-Payload-Digest')
            #Our patched warc-tools fabricates this header if it is not present in the record
            return digest.replace('sha1:', '')
        elif 'response' == record.type and self.content is not None:
            # This is an arc record, and doesn't have the sha1 in the
            # WARC-Payload-Digest header. We calculate the sha1 of the content
            # after stripping off the http headers. If this is a HTTP response,
            # self.content will contain the response without http headers.
            #print repr(self.content)
            #print len(self.content)
            #print len(record.content[1])
            #print base64.b32encode(hashlib.sha1(self.content.strip()).digest())

            #Our patched warc-tools fabricates this header even for arc files
            #so that we can skip large payloads
            digest = record.get_header('WARC-Payload-Digest')
            if digest is not None:
                return digest.replace('sha1:', '')
            else:
                h = hashlib.sha1(self.content)
                return base64.b32encode(h.digest())
        else:
            h = hashlib.sha1(record.content[1])
            return base64.b32encode(h.digest())

    # get_mime_type() //field "m"
    #___________________________________________________________________________
    def get_mime_type(self, record, use_precalculated_value=True):
        """ See the WARC spec for more info on 'application/http; msgtype=response'
        http://archive-access.sourceforge.net/warc/warc_file_format-0.16.html#anchor7
        """

        if use_precalculated_value:
            return self.mime_type

        if 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            mime_type = self.parse_http_content_type_header(record)
        elif 'response' == record.type:
            if record.content_type is None:
                mime_type = 'unk'
            else:
                #alexa arc files use 'no-type' instead of 'unk'
                mime_type = record.content_type.replace('no-type', 'unk')
        elif 'warcinfo' == record.type:
            mime_type = 'warc-info'
        else:
            mime_type = 'warc/'+record.type

        try:
            mime_type = mime_type.decode('ascii')
        except (LookupError, UnicodeDecodeError):
            mime_type = u'unk'

        return mime_type


    # to_unicode()
    #___________________________________________________________________________
    @classmethod
    def to_unicode(self, s, charset):
        if isinstance(s, str):
            if charset is None:
                #try utf-8 and hope for the best
                s = s.decode('utf-8', 'replace')
            else:
                try:
                    s = s.decode(charset, 'replace')
                except LookupError:
                    s = s.decode('utf-8', 'replace')
        return s

    # urljoin_and_normalize()
    #___________________________________________________________________________
    @classmethod
    def urljoin_and_normalize(self, base, url, charset):
        """urlparse.urljoin removes blank fragments (trailing #),
        even if allow_fragments is set to True, so do this manually.

        Also, normalize /../ and /./ in url paths.

        Finally, encode spaces in the url with %20 so that we can
        later split on whitespace.

        Usage (run doctests with  `python -m doctest -v cdx_writer.py`):
        >>> base = 'http://archive.org/a/b/'
        >>> url  = '/c/d/../e/foo'
        >>> print CDX_Writer.urljoin_and_normalize(base, url, 'utf-8')
        http://archive.org/c/e/foo

        urljoin() doesn't normalize if the url starts with a slash, and
        os.path.normalize() has many issues, so normalize using regexes

        >>> url = '/foo/./bar/#'
        >>> print CDX_Writer.urljoin_and_normalize(base, url, 'utf-8')
        http://archive.org/foo/bar/#

        >>> base = 'http://archive.org'
        >>> url = '../site'
        >>> print CDX_Writer.urljoin_and_normalize(base, url, 'utf-8')
        http://archive.org/site

        >>> base = 'http://www.seomoz.org/page-strength/http://www.example.com/'
        >>> url  = 'http://www.seomoz.org/trifecta/fetch/page/http://www.example.com/'
        >>> print CDX_Writer.urljoin_and_normalize(base, url, 'utf-8')
        http://www.seomoz.org/trifecta/fetch/page/http://www.example.com/
        """

        url  = self.to_unicode(url, charset)

        #the base url is from the arc/warc header, which doesn't specify a charset
        base = self.to_unicode(base, 'utf-8')

        try:
            joined_url = urlparse.urljoin(base, url)
        except ValueError:
            #some urls we find in arc files no longer parse with python 2.7,
            #e.g. 'http://\x93\xe0\x90E\x83f\x81[\x83^\x93\xfc\x97\xcd.com/'
            return '-'

        # We were using os.path.normpath, but had to add too many patches
        # when it was doing the wrong thing, such as turning http:// into http:/
        m = re.match('(https?://.+?/)', joined_url)
        if m:
            domain = joined_url[:m.end(1)]
            path   = joined_url[m.end(1):]
            if path.startswith('../'):
                path = path[3:]
            norm_url = domain + re.sub('/[^/]+/\.\./', '/', path)
            norm_url = re.sub('/\./', '/', norm_url)
        else:
            norm_url = joined_url

        # deal with empty query strings and empty fragments, which
        # urljoin sometimes removes
        if url.endswith('?') and not norm_url.endswith('?'):
            norm_url += '?'
        elif url.endswith('#') and not norm_url.endswith('#'):
            norm_url += '#'

        #encode spaces
        return norm_url.replace(' ', '%20')


    # get_redirect() //field "r"
    #___________________________________________________________________________
    def get_redirect(self, record):
        """Aaron, Ilya, and Kenji have proposed using '-' in the redirect column
        unconditionally, after a discussion on Sept 5, 2012. It tirms pit the
        redirect column of the cdx has no effect on the Wayback Machine, and
        there were issues with parsing unescaped characters found in redirects.
        """
        return '-'

        # response_code = self.response_code
        #
        # ## It turns out that the refresh tag is being used in both 2xx and 3xx
        # ## responses, so always check both the http location header and the meta
        # ## tags. Also, the java version passes spaces through to the cdx file,
        # ## which might break tools that split cdx lines on whitespace.
        #
        # #only deal with 2xx and 3xx responses:
        # #if 3 != len(response_code):
        # #    return '-'
        #
        # charset = self.parse_charset()
        #
        # #if response_code.startswith('3'):
        # location = self.parse_http_header('location')
        # if location:
        #     return self.urljoin_and_normalize(record.url, location, charset)
        # #elif response_code.startswith('2'):
        # if self.meta_tags and 'refresh' in self.meta_tags:
        #     redir_loc = self.meta_tags['refresh']
        #     m = re.search('\d+\s*;\s*url=(.+)', redir_loc, re.I) #url might be capitalized
        #     if m:
        #         return self.urljoin_and_normalize(record.url, m.group(1), charset)
        #
        # return '-'

    # get_response_code() //field "s"
    #___________________________________________________________________________
    def get_response_code(self, record, use_precalculated_value=True):
        if use_precalculated_value:
            return self.response_code

        if 'response' != record.type:
            return '-'

        m = re.match("HTTP(?:/\d\.\d)? (\d+)", record.content[1])
        if m:
            return m.group(1)
        else:
            return '-'

    # split_headers_and_content()
    #___________________________________________________________________________
    def parse_headers_and_content(self, record):
        """Returns a list of header lines, split with splitlines(), and the content.
        We call splitlines() here so we only split once, and so \r\n and \n are
        split in the same way.
        """

        if 'response' == record.type and record.content[1].startswith('HTTP'):
            try:
                headers, content = self.crlf_pattern.split(record.content[1], 1)
            except ValueError:
                headers = record.content[1]
                content = None
            headers = headers.splitlines()
        else:
            headers = None
            content = None

        return headers, content

    # make_cdx()
    #___________________________________________________________________________
    def make_cdx(self):
        print ' CDX ' + self.format #print header

        if not self.all_records:
            #filter cdx lines if --all-records isn't specified
            allowed_record_types     = set(['response', 'revisit'])
            disallowed_content_types = set(['text/dns'])

        fh = ArchiveRecord.open_archive(self.file, gzip="auto", mode="r")
        for (offset, record, errors) in fh.read_records(limit=None, offsets=True):
            self.offset = offset

            if record:
                if not self.all_records and (record.type not in allowed_record_types or record.content_type in disallowed_content_types):
                    continue

                ### arc files from the live web proxy can have a negative content length and a missing payload
                ### check the content_length from the arc header, not the computed payload size returned by record.content_length
                content_length_str = record.get_header(record.CONTENT_LENGTH)
                if content_length_str is not None and int(content_length_str) < 0:
                    continue

                ### precalculated data that is used multiple times
                self.headers, self.content = self.parse_headers_and_content(record)
                self.mime_type             = self.get_mime_type(record, use_precalculated_value=False)
                self.response_code         = self.get_response_code(record, use_precalculated_value=False)
                self.meta_tags             = self.parse_meta_tags(record)

                s = u''
                for field in self.format.split():
                    if not field in self.field_map:
                        sys.exit('Unknown field: ' + field)

                    endpoint = self.field_map[field].replace(' ', '_')
                    response = getattr(self, 'get_' + endpoint)(record)
                    #print self.offset
                    #print record.compressed_record_size
                    #print record.content_length
                    #print record.headers
                    #print len(self.content)
                    #print repr(record.content[1])
                    #print endpoint
                    #print repr(response)
                    s += response + ' '
                print s.rstrip().encode('utf-8')
                #record.dump()
            elif errors:
                pass # ignore
            else:
                pass # tail

        fh.close()

# main()
#_______________________________________________________________________________
if __name__ == '__main__':

    parser = OptionParser(usage="%prog [options] warc.gz")
    parser.set_defaults(format        = "N b a m s k r M S V g",
                        use_full_path = False,
                        file_prefix   = None,
                        all_records   = False,
                       )

    parser.add_option("--format",  dest="format", help="A space-separated list of fields [default: '%default']")
    parser.add_option("--use-full-path", dest="use_full_path", action="store_true", help="Use the full path of the warc file in the 'g' field")
    parser.add_option("--file-prefix",   dest="file_prefix", help="Path prefix for warc file name in the 'g' field."
                      " Useful if you are going to relocate the warc.gz file after processing it."
                     )
    parser.add_option("--all-records",   dest="all_records", action="store_true", help="By default we only index http responses. Use this flag to index all WARC records in the file")

    (options, input_files) = parser.parse_args(args=sys.argv[1:])

    if not 1 == len(input_files):
        parser.print_help()
        exit(-1)

    cdx_writer = CDX_Writer(input_files[0], options.format,
                            use_full_path = options.use_full_path,
                            file_prefix   = options.file_prefix,
                            all_records   = options.all_records,
                           )
    cdx_writer.make_cdx()
