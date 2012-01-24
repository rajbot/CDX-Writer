Python script to create CDX index files of WARC data.

Usage:
`cdx_writer.py [--format format_str] file.warc.gz`

`--format` flag specifies the list of fields to include. If `--format`
is not supplied, the default format "N b a m s k r M S V g" is used.

Output is written to stdout. The first line of output is the CDX header.
This header line begins with a space so that the cdx file can be passed
through `sort` while keeping the header at the top.

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
