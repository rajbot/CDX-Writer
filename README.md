Python script to create CDX index files of WARC data.

`--format` flag specifies the list of fields to include.

The syntax is as follows (from http://www.archive.org/web/researcher/cdx_legend.php):

    The default first line of a CDX file is :
    CDX A b e a m s c k r V v D d g M n


    The letters use in dat files and cdx files are as follows :

    A canonized url
    B news group
    C rulespace category ***
    D compressed dat file offset
    F canonized frame
    G multi-columm language description (* soon)
    H canonized host
    I canonized image
    J canonized jump point
    K Some weird FBIS what's changed kinda thing
    L canonized link
    M meta tags (AIF) *
    N massaged url
    P canonized path
    Q language string
    R canonized redirect
    U uniqness ***
    V compressed arc file offset *
    X canonized url in other href tages
    Y canonized url in other src tags
    Z canonized url found in script
    a original url **
    b date **
    c old style checksum *
    d uncompressed dat file offset
    e IP **
    f frame *
    g file name
    h original host
    i image *
    j original jump point
    k new style checksum *
    l link *
    m mime type of original document *
    n arc document length *
    o port
    p original path
    r redirect *
    s response code *
    t title *
    v uncompressed arc file offset *
    x url in other href tages *
    y url in other src tags *
    z url found in script *
    # comment

    * in alexa-made dat file
    ** in alexa-made dat file meta-data line
    *** future data
