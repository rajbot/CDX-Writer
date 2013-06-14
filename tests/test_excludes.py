#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess


tests = [
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://www.sueddeutsche.de',
        'result' : """vn,rolo,art)/a/chi-tiet/021826271565622/ngoc-trinh-xinh-tuoi-o-hoi-an 20110804181044 http://art.rolo.vn:80/a/chi-tiet/021826271565622/ngoc-trinh-xinh-tuoi-o-hoi-an unk 404 3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ - - 229 162 uncompressed.arc
com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc"""
    },
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://art.rolo.vn/a/',
        'result' : """de,sueddeutsche)/muenchen/manu-chao-in-muenchen-che-guitarra-1.1114509-2 20110804181044 http://www.sueddeutsche.de:80/muenchen/manu-chao-in-muenchen-che-guitarra-1.1114509-2 text/html 200 ZMBIXCVTXG2CNEFAZI753FJUXJUQSI2M - A 78939 392 uncompressed.arc
com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc"""
    },
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://www.sueddeutsche.de\nhttp://art.rolo.vn/a/',
        'result' : """com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc"""
    }
]

test_num = 0
for test in tests:
    test_file = test['file']
    exclude_list = 'tmp_excludes.txt'

    assert os.path.exists(test_file)
    assert not os.path.exists(exclude_list)

    print "processing #", test_num, test_file

    f = open(exclude_list, 'w')
    f.write(test['exclude'] + '\n')
    f.close()

    cmd = ['../cdx_writer.py', '--all-records', '--exclude-list='+exclude_list, test_file]

    output = subprocess.check_output(cmd)

    os.unlink(exclude_list)

    assert output.strip().endswith(test['result']), """\n  expected: %s\n       got: %s\n""" % (test['result'], '\n'.join(output.split('\n')[1:]))
    test_num += 1

print "exiting without errors!"
