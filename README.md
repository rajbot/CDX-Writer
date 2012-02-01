# cdx_writer.py
Python script to create CDX index files of WARC data.

## Usage
Usage: `cdx_writer.py [options] warc.gz`

Options:

    -h, --help            show this help message and exit
    --format=FORMAT       A space-separated list of fields [default: 'N b a m s k r M S V g']
    --use-full-path       Use the full path of the warc file in the 'g' field
    --file-prefix=PREFIX  Path prefix for warc file name in the 'g' field.
                          Useful if you are going to relocate the warc.gz file
                          after processing it.
    --all-records         By default we only index http responses. Use this flag
                          to index all WARC records in the file.


Output is written to stdout. The first line of output is the CDX header.
This header line begins with a space so that the cdx file can be passed
through `sort` while keeping the header at the top.

## Format
The supported format options are:

    M meta tags (AIF) *
    N massaged url
    S compressed record size
    V compressed arc file offset *
    a original url **
    b date **
    g file name
    k new style checksum *
    m mime type of original document *
    r redirect *
    s response code *

    * in alexa-made dat file
    ** in alexa-made dat file meta-data line

More information about the CDX format syntax can be found here:
http://www.archive.org/web/researcher/cdx_legend.php


## Differences between cdx_writer.py and access-access cdx files
The CDX files produced by the [archive-access](http://sourceforge.net/projects/archive-access/)
produce different CDX lines in these cases:

### Differences in SURTs:
* archive-access doesn't encode the %7F character in SURTs

### Differences in MIME Type:
* archive-access does not parse mime type for large warc payloads, and just returns 'unk'
* archive-access returns a "close" mime type when a Connection: close header is sent, then a Content-Type HTTP header is sent with a blank value, and then the connection is immediately closed.
cdx_writer.py returns 'unk' in this case. Example WARC Record:
    <code>...Content-Length: 0\r\nConnection: close\r\nContent-Type: \r\n\r\n\r\n\r\n</code>

### Differences in Redirect urls:
* archive-access does not escape whitespace, cdx_writer.py uses %20 escaping so we can split these files on whitespace.
* archive-access removes unicode characters from redirect urls, cdx_writer.py version keeps them
* archive-access sometimes doesn't turn relative URLs into absolute urls
* archive-access sometimes does not remove /../ from redirect urls
* archive-access uses the value from the previous HTTP header for the redirect url if the location header is empty
* cdx_writer.py only looks for http-equiv=refresh meta tag inside head elements

### Differences in Meta Tags:
* cdx_writer.py only looks for meta tags in the head element
* cdx_writer.py uses lxml.html, which sometimes incorrectly parses meta tags as children of the body element instead of the head
* archive-access version doesn't parse multiple html meta tags, only the first one
* archive-access misses FI meta tags sometimes
* cdx_writer.py always returns tags in A, F, I order. archive-access does not use a consistent order


### Differences in HTTP Response Codes
* archive-access returns response code 0 if HTTP header line contains unicode:
    <code>HTTP/1.1 302 D\xe9plac\xe9 Temporairement\r\n...</code>
