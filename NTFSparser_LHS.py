# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ntfs_gui.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(840, 630)
        self.verticalLayout = QtGui.QVBoxLayout(Form)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.lineEdit = QtGui.QLineEdit(Form)
        self.lineEdit.setObjectName(_fromUtf8("lineEdit"))
        self.lineEdit.setToolTip(_fromUtf8("click right button to select directory"))
        self.horizontalLayout.addWidget(self.lineEdit)
        self.pushButton = QtGui.QPushButton(Form)
        self.pushButton.setObjectName(_fromUtf8("pushButton"))
        self.pushButton.setToolTip(_fromUtf8("click to select directory"))
        self.horizontalLayout.addWidget(self.pushButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.webView = QtWebKit.QWebView(Form)
        self.webView.setUrl(QtCore.QUrl(_fromUtf8("about:blank")))
        self.webView.setObjectName(_fromUtf8("webView"))
        self.webView.setToolTip(_fromUtf8("결과가 html 형식으로 보여지는 곳입니다."))
        self.verticalLayout.addWidget(self.webView)

        # for select dir
        self.dialog = QtGui.QFileDialog()
        self.dialog.setFileMode(QtGui.QFileDialog.Directory)
        self.dialog.setOption(QtGui.QFileDialog.ShowDirsOnly)      
        self.alarm = QtGui.QMessageBox()
        self.alarm.setWindowTitle(u"알림")
        self.alarm.setText(u"indexes.html 파일로 저장되었습니다.")
        
        # signal control
        self.pushButton.clicked.connect(self.selectdir)
 
        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "NTFS Parser - LHS", None))
        self.pushButton.setText(_translate("Form", "폴더 선택", None))

    def selectdir(self):
        if self.dialog.exec_():
            filename = self.dialog.selectedFiles()[0]
            self.lineEdit.setText(filename)
            ntfs_parse(filename)
            self.webView.setUrl(QtCore.QUrl(_fromUtf8("indexs.html")))
            self.alarm.show()
    
from PyQt4 import QtWebKit

import os
from datetime import datetime,timedelta

def time64bit(dt):
    us = dt / 10.
    return str(datetime(1601,1,1,9) + timedelta(microseconds=us))

# make Little endian hex to Big endian decimal
def LtoB(buf):
    val = 0
    for i in range(0, len(buf)):
        multi=1
        for j in range(0,i):
            multi *= 256
        val += buf[i] * multi
    return val

# find MFT entry from VCN
def MFTfromVCN(fp, iaa, vcn, name):
    start = LtoB(iaa[0x10:0x18])
    end = LtoB(iaa[0x18:0x20])
    offset = LtoB(iaa[0x20:0x22])
    if (vcn > end) or (vcn < start):
        print_err('vcn error')
        return -1
    avcn = vcn - start
    cluster_run = iaa[offset:]
    ptr = 0
    address = 0
    while True:
        if cluster_run[ptr] == 0:
            print_err('cluster run error')
            return -1
        rl = cluster_run[ptr] & 0xF # run length position
        add_len = cluster_run[ptr] >> 4 # address length
        run_len = LtoB(cluster_run[ptr+1:ptr+1+rl]) # run length
        if avcn < run_len:
            address += LtoB(cluster_run[ptr+1+rl:ptr+1+rl+add_len])*0x1000+0x1000*(avcn) # sector * cluster
            break
        else:
            address += LtoB(cluster_run[ptr+1+rl:ptr+1+rl+add_len])*0x1000 # sector * cluster
            avcn -= run_len
            ptr += 1 + rl + add_len
    
    # read INDX
    fp.seek(address)
    indx = bytearray(fp.read(0x1000))
    if indx[0:4] != 'INDX':
        print_err('indx file reference error')
        return -1
    # fixup
    fixup = LtoB(indx[0x04:0x06])
    fixup_len = LtoB(indx[0x06:0x08])
    for i in range(1,fixup_len):
        indx[0x200*i-2] = indx[fixup+i*2]
        indx[0x200*i-1] = indx[fixup+i*2+1]
    offset = LtoB(indx[0x18:0x1C])
    fin = LtoB(indx[0x1C:0x20])
    ne = 0x18+offset
    while True:
        ne_len = LtoB(indx[ne+0x08:ne+0x0A])
        node_entry = indx[ne:ne+ne_len]
        flag = LtoB(indx[ne+0x0C:ne+0x10]) & 0x03
        if flag == 0x02:
            #print 'end node and no child (error: no such directory)'
            return -1
        elif flag == 0x03:
            vcn = LtoB(indx[-0x08:])
            return MFTfromVCN(fp, iaa, vcn, name)
        fname_len = node_entry[0x50]*2 # multi byte
        fname = u''.join(node_entry[0x50+2:0x50+2+fname_len].decode('utf-16'))
        fname = fname.encode('utf-8')
        fname = QtCore.QString.fromUtf8(fname)
        name = QtCore.QString.fromUtf8(name)
        fname = fname.toUpper()
        name = name.toUpper()
        fname = str(fname.toUtf8())
        name = str(name.toUtf8())
        if fname == name:
            return LtoB(node_entry[0:6])
        elif fname > name:
            if flag != 0x1:
                # no vcn
                #print "error"
                return -1
            vcn = LtoB(node_entry[ne_len-0x08:])
            return MFTfromVCN(fp, iaa,vcn,name)
        else:
            ne += ne_len
    
# find VCN from index root
# this function returns MFT entry number
def FindMFTentry(fp, ira, iaa, name):
    # ira에서 루트 노드에 있는가.
    ne = 0x40
    while True:
        ne_len = LtoB(ira[ne+0x8:ne+0x8+2])
        node_entry = ira[ne:ne+ne_len]
        flag = LtoB(node_entry[0x0C:0x10]) & 0x3
        if flag == 0x2:
            # end of node but no vcn
            #print "error"
            return -1
        elif flag == 0x03:
            # end of node and have vcn
            vcn = LtoB(node_entry[ne_len-0x08:])
            return MFTfromVCN(fp, iaa, vcn, name)
        fname_len = node_entry[0x50]*2 # multi byte
        fname = u''.join(node_entry[0x50+2:0x50+2+fname_len].decode('utf-16'))
        fname = fname.encode('utf-8')
        fname = QtCore.QString.fromUtf8(fname)
        name = QtCore.QString.fromUtf8(name)
        fname = fname.toUpper()
        name = name.toUpper()
        fname = str(fname.toUtf8())
        name = str(name.toUtf8())
        # root node
        if fname == name:
            return LtoB(node_entry[0:6])
        # left (VCN)
        elif fname > name:
            if flag != 0x1:
                # no vcn
                return -1
            vcn = LtoB(node_entry[ne_len-0x08:])
            return MFTfromVCN(fp, iaa,vcn,name)
        # right (next root node)
        else:
            ne += ne_len

def allMFTfromVCN(fp, iaa, vcn):
    ret = []
    start = LtoB(iaa[0x10:0x18])
    end = LtoB(iaa[0x18:0x20])
    offset = LtoB(iaa[0x20:0x22])
    if (vcn > end) or (vcn < start):
        #print 'vcn error'
        ret.append(-1)
        return ret
    
    avcn = vcn - start
    cluster_run = iaa[offset:]
    ptr = 0
    address = 0
    while True:
        if cluster_run[ptr] == 0:
            #print 'cluster run error'
            return [-1]
        rl = cluster_run[ptr] & 0xF # run length position
        add_len = cluster_run[ptr] >> 4 # address length
        run_len = LtoB(cluster_run[ptr+1:ptr+1+rl]) # run length
        add = LtoB(cluster_run[ptr+1+rl:ptr+1+rl+add_len])
        chk = add >> (add_len*8-1)
        if chk == 1:
            add = 0 - ((add^((1 << (add_len*8)) - 1)) + 1)
        if avcn < run_len:
            address += add*0x1000+0x1000*(avcn) # sector * cluster
            break
        else:
            address += add*0x1000 # sector * cluster
            avcn -= run_len
            ptr += 1 + rl + add_len
    
    # read INDX
    fp.seek(address)
    indx = bytearray(fp.read(0x1000))
    if indx[0:4] != 'INDX':
        #print 'indx file reference error'
        return [-1]
    # fixup
    fixup = LtoB(indx[0x04:0x06])
    fixup_len = LtoB(indx[0x06:0x08])
    for i in range(1,fixup_len):
        indx[0x200*i-2] = indx[fixup+i*2]
        indx[0x200*i-1] = indx[fixup+i*2+1]
    offset = LtoB(indx[0x18:0x1C])
    fin = LtoB(indx[0x1C:0x20])
    ne = 0x18+offset
    while True:
        ne_len = LtoB(indx[ne+0x08:ne+0x0A])
        node_entry = indx[ne:ne+ne_len]
        flag = LtoB(indx[ne+0x0C:ne+0x10]) & 0x03
        if flag == 0x02:
            return ret
        elif flag == 0x03:
            vcn = LtoB(indx[-0x08:])
            return ret + allMFTfromVCN(fp, iaa, vcn)
        
        if flag == 0x01:
            vcn = LtoB(node_entry[ne_len-0x08:])
            ret += allMFTfromVCN(fp,iaa,vcn)
        
        ret.append(LtoB(node_entry[0:6]))
        
        ne += ne_len


# get all children's mft entries index buffer
# it returns array of children's mft entries
def ChildMFTs(fp, ira, iaa):
    ret = []
    ne = 0x40
    while True:
        ne_len = LtoB(ira[ne+0x8:ne+0x8+2])
        node_entry = ira[ne:ne+ne_len]    
        flag = LtoB(node_entry[0x0C:0x10]) & 0x3
        if flag == 0x2:
            # end of index root node and no vcn
            real_ret = []
            # remove repeated MFTs (long name causes repeat)
            for i in ret:
                if i not in real_ret:
                    real_ret.append(i)
            return real_ret
        elif flag == 0x03:
            # end of node and have vcn
            vcn = LtoB(node_entry[ne_len-0x08:])
            # do cluster run
            ret += allMFTfromVCN(fp,iaa,vcn)
            real_ret = []
            # remove repeated MFTs (long name causes repeat)
            for i in ret:
                if i not in real_ret:
                    real_ret.append(i)
            return real_ret
            
        if flag == 0x1:
            # it has filename node and also has left child
            vcn = LtoB(node_entry[ne_len-0x08:])
            # do cluster run
            ret += allMFTfromVCN(fp,iaa,vcn)
            
        # append this node's MFT entry
        ret.append(LtoB(node_entry[0:6]))
        
        ne += ne_len

def NameMFT(fp, mft_offsets, mft_num):
    # go to mft
    MFTentry_num = mft_num
    mft_offset = 0
    for i in range(len(mft_offsets)/2):
        mft_offset += mft_offsets[2*i]
        if(MFTentry_num < (mft_offsets[2*i+1]*4)):
            break
        else:
            MFTentry_num -= mft_offsets[2*i+1]*4
            
    fp.seek(mft_offset + MFTentry_num*0x400)
    mft = bytearray(fp.read(0x400))
    if mft[0:4] != 'FILE':
        #print 'reading mft error'
        #sys.exit()
        return u"error"
    # fixup
    fixup = LtoB(mft[4:6])
    mft[0x200-2] = mft[fixup+2]
    mft[0x200-1] = mft[fixup+3]
    mft[0x400-2] = mft[fixup+4]
    mft[0x400-1] = mft[fixup+5]
    
    # find filename attr
    attr = 0x38
    fna = []
    ira = []
    iaa = []
    name = ""
    while True:
        att_type = LtoB(mft[attr:attr+4])
        att_len = LtoB(mft[attr+4:attr+8])
        # end of mft entry
        if att_type == 0xFFFFFFFF:
            return name
        
        # filename attr
        if att_type == 0x30:
            fna = mft[attr:attr+att_len]
            fn = LtoB(fna[0x14:0x16])+0x40
            filename = fna[fn+2:fn+2+(fna[fn]*2)]
            tmp = u''.join(filename.decode('utf-16'))
            if (len(tmp) > len(name)) and (u'~1' not in tmp):
                name = tmp
        
        attr += att_len
        # end of mft entry
        if attr >= 0x400:
            #print 'error'
            return name

def print_err(msg):
    a = QtGui.QMessageBox()
    a.setWindowTitle("Error")
    a.setText(msg)
    a.exec_()    

def ntfs_parse(path):
    path = path.toUtf8()
    if path[-1] != '/':
        path += '/'
    path_split = path.split('/')
    curr = 0
    try:
        f = open('//./'+path_split[0],'rb')
        curr += 1
    except:
        print_err(u'관리자 권한이 필요합니다.')
        sys.exit()
    
    f.seek(0)
    # read vbr
    vbr = bytearray(f.read(0x200))
    
    # check ntfs
    if vbr[3:7] != "NTFS":
        print_err(u'error: 경로가 NTFS 시스템이 아닙니다.')
        #sys.exit()
        return
    
    # sector size (byte)
    sec = LtoB(vbr[0x0B:0x0C+1])
    # cluster size (n sector)
    clu = vbr[0x0D]
    
    # MFT entry offset
    mft_offset = LtoB(vbr[0x30:0x38])*sec*clu
    
    # MFT entry cluster run ####################
    f.seek(mft_offset)
    mft = bytearray(f.read(0x400))
    if mft[0:4] != 'FILE':
        print_err(u"reading MFT's mft error")
        #sys.exit()
        return
    # fixup
    fixup = LtoB(mft[4:6])
    mft[0x200-2] = mft[fixup+2]
    mft[0x200-1] = mft[fixup+3]
    mft[0x400-2] = mft[fixup+4]
    mft[0x400-1] = mft[fixup+5]
    
    # find data attr
    attr = 0x38
    data = []
    # get data attr
    while True:
        att_type = LtoB(mft[attr:attr+4])
        att_len = LtoB(mft[attr+4:attr+8])
        
        # end of mft entry
        if att_type == 0xFFFFFFFF:
            print_err(u"error: there is no data attr")
            break
        
        # data attr
        if att_type == 0x80:
            data = mft[attr:attr+att_len]
            cluster_run = data[0x40:]
            mft_offsets = []
            ptr = 0
            while True:
                if cluster_run[ptr] == 0:
                    #print mft_offsets
                    break
                rl = cluster_run[ptr] & 0xF # run length position
                add_len = cluster_run[ptr] >> 4 # address length
                run_len = LtoB(cluster_run[ptr+1:ptr+1+rl]) # run length
                add = LtoB(cluster_run[ptr+1+rl:ptr+1+rl+add_len])
                chk = add >> (add_len*8-1)
                if chk == 1:
                    add = 0 - ((add^((1 << (add_len*8)) - 1)) + 1)
                mft_offsets.append(add*0x1000)
                mft_offsets.append(run_len)
                ptr += 1 + rl + add_len            
            break
        attr += att_len
        # end of mft entry
        if attr >= 0x400:
            print_err(u"error: MFT has no data attr")
            #sys.exit()
            return
    
    
    ############################################
    
    # go to mft
    f.seek(mft_offset + 5*0x400)
    mft = bytearray(f.read(0x400))
    if mft[0:4] != 'FILE':
        print_err(u'reading root mft error. line:451')
        #sys.exit()
        return
    
    # fixup
    fixup = LtoB(mft[4:6])
    mft[0x200-2] = mft[fixup+2]
    mft[0x200-1] = mft[fixup+3]
    mft[0x400-2] = mft[fixup+4]
    mft[0x400-1] = mft[fixup+5]
    
    # directory check
    flag = LtoB(mft[0x16:0x18])
    if (flag & 0x2) == 0:
        print_err(u"디렉토리가 아닙니다.")
        #sys.exit()
        return
    
    # find filename attr
    attr = 0x38
    fna = []
    ira = []
    iaa = []
    while True:
        att_type = LtoB(mft[attr:attr+4])
        att_len = LtoB(mft[attr+4:attr+8])
        
        # end of mft entry
        if att_type == 0xFFFFFFFF:
            break
        
        # filename attr
        if att_type == 0x30:
            fna = mft[attr:attr+att_len]
            fn = LtoB(fna[0x14:0x16])+0x40
            filename = fna[fn+2:fn+2+(fna[fn]*2)]
            
        # index root attr
        elif att_type == 0x90:
            ira = mft[attr:attr+att_len]
            
        # index allocation attr
        elif att_type == 0xA0:
            iaa = mft[attr:attr+att_len]
            
        attr += att_len
        # end of mft entry
        if attr >= 0x400:
            break
    
    # current path
    a = u''.join(filename.decode('utf-16'))
    
    # directory traversing
    while path_split[curr] != '':
        MFTentry_num = FindMFTentry(f, ira,iaa,path_split[curr])
        
        if MFTentry_num == -1:
            print_err(str(path_split[curr])+u': no such directory')
        else:
            # go to mft
            mft_offset = 0
            for i in range(len(mft_offsets)/2):
                mft_offset += mft_offsets[2*i]
                if(MFTentry_num < (mft_offsets[2*i+1]*4)):
                    break
                else:
                    MFTentry_num -= mft_offsets[2*i+1]*4
                    
            f.seek(mft_offset + MFTentry_num*0x400)
            mft = bytearray(f.read(0x400))
            if mft[0:4] != 'FILE':
                print_err(str(path_split[curr])+u' - reading mft error.\nMFT entry num:'+str(MFTentry_num))
                #sys.exit()
                return
            
            # fixup
            fixup = LtoB(mft[4:6])
            mft[0x200-2] = mft[fixup+2]
            mft[0x200-1] = mft[fixup+3]
            mft[0x400-2] = mft[fixup+4]
            mft[0x400-1] = mft[fixup+5]
            
            # directory check
            flag = LtoB(mft[0x16:0x18])
            if (flag & 0x2) == 0:
                print_err(str(path_split[curr])+u"는 디렉토리가 아닙니다.")
                return
            
            # find filename attr
            attr = 0x38
            fna = []
            ira = []
            iaa = []
            while True:
                att_type = LtoB(mft[attr:attr+4])
                att_len = LtoB(mft[attr+4:attr+8])
                
                # end of mft entry
                if att_type == 0xFFFFFFFF:
                    break
                
                # filename attr
                if att_type == 0x30:
                    fna = mft[attr:attr+att_len]
                    fn = LtoB(fna[0x14:0x16])+0x40
                    filename = fna[fn+2:fn+2+(fna[fn]*2)]
                    
                # index root attr
                elif att_type == 0x90:
                    ira = mft[attr:attr+att_len]
                    
                # index allocation attr
                elif att_type == 0xA0:
                    iaa = mft[attr:attr+att_len]
                    
                attr += att_len
                # end of mft entry
                if attr >= 0x400:
                    break
            # current path
            a = u''.join(filename.decode('utf-16'))
            ##print a + u"의 MFT entry 번호: " + str(MFTentry_num)
            ##print LtoB(mft[0x2C:0x30])
        curr += 1
    
    # go to input directory MFT entry (it already loaded at 'mft' array)
    child_mfts = ChildMFTs(f, ira, iaa)
    
    if child_mfts.count(-1) > 0:
        print child_mfts
        print_err(u'하위 경로의 MFT 번호 중 오류가 있습니다.')
        #sys.exit()
    
    outhtml = open('indexs.html','wb')
    
    html_title = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n\n<!-- Latest compiled and minified CSS -->\n<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous">\n\n<!-- Optional theme -->\n<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css" integrity="sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp" crossorigin="anonymous">\n\n<!-- Latest compiled and minified JavaScript -->\n<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js" integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa" crossorigin="anonymous"></script>\n\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n<title>Index of '
    html_middle = '</title>\n<meta name="keywords" content="" />\n<meta name="description" content="" />\n<link href="http://fonts.googleapis.com/css?family=Source+Sans+Pro:200,300,400,600,700,900" rel="stylesheet" />\n</head>\n<body>\n\n<h1>Index of '
    html_table = '</h1>\n<br><br>\n<table class="table table-bordered table-hover" style="width:90%; margin:0 auto" id="indexes">\n<tr align="center"><td>순번 <a onclick="sortTable(true, 0)" style="cursor:pointer">△</a><a onclick="sortTable(false, 0)" style="cursor:pointer">▽</a></td><td>파일명 <a onclick="sortTable(true, 1)" style="cursor:pointer">△</a><a onclick="sortTable(false, 1)" style="cursor:pointer">▽</a></td><td>크기(byte) <a onclick="sortTable(true, 2)" style="cursor:pointer">△</a><a onclick="sortTable(false, 2)" style="cursor:pointer">▽</a></td><td>MFT entry <a onclick="sortTable(true, 3)" style="cursor:pointer">△</a><a onclick="sortTable(false, 3)" style="cursor:pointer">▽</a></td><td>Create time <a onclick="sortTable(true, 4)" style="cursor:pointer">△</a><a onclick="sortTable(false, 4)" style="cursor:pointer">▽</a></td><td>Modify time <a onclick="sortTable(true, 5)" style="cursor:pointer">△</a><a onclick="sortTable(false, 5)" style="cursor:pointer">▽</a></td><td>Entry Modified time <a onclick="sortTable(true, 6)" style="cursor:pointer">△</a><a onclick="sortTable(false, 6)" style="cursor:pointer">▽</a></td><td>Access time <a onclick="sortTable(true, 7)" style="cursor:pointer">△</a><a onclick="sortTable(false, 7)" style="cursor:pointer">▽</a></td></tr>'
    html_end = '</table>\n<script>\nfunction sortTable(updown, pos) {\n  var table, rows, switching, i, x, y, shouldSwitch;\n  table = document.getElementById("indexes");\n  switching = true;\n  /*Make a loop that will continue until\n  no switching has been done:*/\n  while (switching) {\n    //start by saying: no switching is done:\n    switching = false;\n    rows = table.getElementsByTagName("TR");\n    /*Loop through all table rows (except the\n    first, which contains table headers):*/\n    for (i = 1; i < (rows.length - 1); i++) {\n      //start by saying there should be no switching:\n      shouldSwitch = false;\n      /*Get the two elements you want to compare,\n      one from current row and one from the next:*/\n      x = rows[i].getElementsByTagName("TD")[pos];\n      y = rows[i + 1].getElementsByTagName("TD")[pos];\n      //check if the two rows should switch place:\n      // if updown=true, up. if updown=false, down.\n      xx = x.innerHTML.toLowerCase();\n      yy = y.innerHTML.toLowerCase();\n      if (pos == 0 || pos == 2 || pos == 3){\n        if(!(xx = Number(xx))){\n          if(xx != 0){xx = -1};\n        }\n        if(!(yy = Number(yy))){\n          if(yy != 0){yy = -1};\n        }\n      }\n      if(updown){\n        if (xx > yy) {\n          //if so, mark as a switch and break the loop:\n          shouldSwitch = true;\n          break;\n        }\n      }\n      else{\n          if (xx < yy) {\n          //if so, mark as a switch and break the loop:\n          shouldSwitch = true;\n          break;\n        }\n      }\n    }\n    if (shouldSwitch) {\n      /*If a switch has been marked, make the switch\n      and mark that a switch has been done:*/\n      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);\n      switching = true;\n    }\n  }\n}\n</script>\n</body>\n</html>'
    outhtml.write(html_title)
    outhtml.write(path_split[-1])
    outhtml.write(html_middle)
    outhtml.write(path)
    outhtml.write(html_table)
    # table content
    for i in range(len(child_mfts)):
        # go to mft
        MFTentry_num = child_mfts[i]
        if MFTentry_num == -1:
            text = ('<tr align="center"><td>'+str(i+1)+'</td><td><a href="'+'">'+'</a></td><td>'+'</td><td>'+'error'+'</td><td>'+'</td><td>'+'</td><td>'+'</td><td>'+'</td></tr>')
            outhtml.write(text)
            continue
        mft_offset = 0
        for j in range(len(mft_offsets)/2):
            mft_offset += mft_offsets[2*j]
            if(MFTentry_num < (mft_offsets[2*j+1]*4)):
                break
            else:
                MFTentry_num -= mft_offsets[2*j+1]*4

        f.seek(mft_offset + MFTentry_num*0x400)
        mft = bytearray(f.read(0x400))
        if mft[0:4] != 'FILE':
            print_err('reading mft error. line:619')
            #sys.exit()
            text = ('<tr align="center"><td>'+str(i+1)+'</td><td><a href="'+'">'+'</a></td><td>'+'</td><td>'+str(child_mfts[i]).encode('utf-8')+'</td><td>'+'</td><td>'+'</td><td>'+'</td><td>'+'</td></tr>')
            outhtml.write(text)
            continue
        
        # fixup
        fixup = LtoB(mft[4:6])
        mft[0x200-2] = mft[fixup+2]
        mft[0x200-1] = mft[fixup+3]
        mft[0x400-2] = mft[fixup+4]
        mft[0x400-1] = mft[fixup+5]
        
        # directory check
        flag = LtoB(mft[0x16:0x18])
        filesize = "0"
        
        filename = NameMFT(f,mft_offsets,child_mfts[i])
        # find $STANDARD_INFORMATION attrs
        attr = 0x38
        att_type = LtoB(mft[attr:attr+4])
        if att_type != 0x10:
            print_err(u'standard information error')
            #sys.exit()
            text = ('<tr align="center"><td>'+str(i+1)+'</td><td><a href="'+'">'+'</a></td><td>'+'</td><td>'+str(child_mfts[i]).encode('utf-8')+'</td><td>'+'</td><td>'+'</td><td>'+'</td><td>'+'</td></tr>')
            outhtml.write(text)
            continue
        att_len = LtoB(mft[attr+4:attr+8])    
        sia = mft[attr:attr+att_len]
        Ctime = time64bit(LtoB(sia[0x18:0x20]))
        Mtime = time64bit(LtoB(sia[0x20:0x28]))
        Etime = time64bit(LtoB(sia[0x28:0x30]))
        Atime = time64bit(LtoB(sia[0x30:0x38]))
        
        attr += att_len
        # not directory
        if (flag & 0x2) == 0:
            # get data attr
            while True:
                att_type = LtoB(mft[attr:attr+4])
                att_len = LtoB(mft[attr+4:attr+8])
                
                # end of mft entry
                if att_type == 0xFFFFFFFF:
                    print_err(u"error: there is no data attr - MFT num:"+str(child_mfts[i]))
                    break
                
                # data attr
                if att_type == 0x80:
                    data = mft[attr:attr+att_len]
                    res_flag = data[0x08] & 0x01
                    # resident attr
                    if res_flag == 0x00:
                        filesize = LtoB(data[0x10:0x14])
                    # non-resident attr
                    else:
                        # byte
                        filesize = (LtoB(data[0x18:0x20]) - LtoB(data[0x10:0x18]))*sec*clu
                    filesize = str(filesize)# + ' Byte'
                    break
                attr += att_len
                # end of mft entry
                if attr >= 0x400:
                    print_err(u"error: there is no data attr")
                    break
            
        else:
            filesize = "directory"
        
        # It has error in zone identifier (can't calc real size)
        
        filename = str(QtCore.QString(filename).toUtf8())
        filesize = str(QtCore.QString(filesize).toUtf8())
        '''
        try:
            text = '<tr align="center"><td>'
            text += str(i+1)+'</td><td><a href="'
            text += path+filename+'">'
            text += filename+'</a></td><td>'
            text += filesize+'</td><td>'
            text +=str(child_mfts[i]).encode('utf-8')
            text +='</td><td>'+Ctime
            text +='</td><td>'+Mtime
            text +='</td><td>'+Etime
            text +='</td><td>'+Atime+'</td></tr>'
        except:
            print text
        '''
        text = ('<tr align="center"><td>'+str(i+1)+'</td><td><a href="'+path+filename+'">'+filename+'</a></td><td>'+filesize+'</td><td>'+str(child_mfts[i]).encode('utf-8')+'</td><td>'+Ctime+'</td><td>'+Mtime+'</td><td>'+Etime+'</td><td>'+Atime+'</td></tr>')
        
        outhtml.write(text)
        
    outhtml.write(html_end)
    
    f.close()
    outhtml.close()    

import sys

if __name__ == "__main__":
    
    app = QtGui.QApplication(sys.argv)
    Form = QtGui.QWidget()
    ui = Ui_Form()
    ui.setupUi(Form)
    Form.show()
    
    
    sys.exit(app.exec_())
