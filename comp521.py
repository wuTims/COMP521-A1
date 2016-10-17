'''Comp521 support module with tools for downloading assignments, lecture notes, and exams
and uploading student submissions.

Gary Bishop Fall 2015
'''

import urllib
import os
import os.path as osp
import urlparse
import json
import time
import hashlib
import pickle
import sqlite3
try:
    import Dee
    gotDee = True
except:
    gotDee = False

Site = 'https://wwwx.cs.unc.edu/Courses/comp521-f15/'

##############################
#
# functions for fetching files
#
##############################

ATTEMPTS = 10

def fileHash(filename):
    '''Compute the checksum to be sure the file is what we expect'''
    BLOCKSIZE = 65536
    hasher = hashlib.sha1()
    with open(filename, 'rb') as fp:
        buf = fp.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = fp.read(BLOCKSIZE)
    return hasher.hexdigest()

def fetchFile(url, filename, check):
    '''Download files to the student's working directory'''
    # make sure the destination folder (if any) exists
    dirname = osp.dirname(filename)
    if dirname and not osp.exists(dirname):
        try:
            os.makedirs(dirname)
        except:
            print 'making folder for %s failed', filename
            return False

    message = ''
    for i in range(ATTEMPTS):
        try:
            filename, headers = urllib.urlretrieve(url, filename)
            if not check or fileHash(filename) == check:
                break
            else:
                message = 'File checksum not correct'

        except IOError:
            message = 'Cannot connect to the server'

        # pause before trying again
        time.sleep(0.1 * i)

    else:
        print 'Too many attempts to fetch file, failing'
        print message
        return False

    return True

def fetchAllFiles(siteURL, listname):
    '''Make sure the student has all the files listed'''
    listURL = urlparse.urljoin(siteURL, listname)
    fp = None
    message = ''
    for i in range(ATTEMPTS):
        try:
            fp = urllib.urlopen(listURL)
            if fp.getcode() == 200:
                data = json.load(fp)
                break

            message = 'fetch failed, for %s' % listname

        except IOError:
            message = 'Cannot connect to server'

        except ValueError:
            message = 'File list appears invalid'

        time.sleep(0.1 * i)

    else:
        print 'Fetching the file list failed, are you connected to a network?'
        if message:
            print message
        if fp:
            print 'code is', fp.getcode()
            print 'url is', listURL
            return -1

    # if we get here, we successfully retrieved the filelist
    count = 0
    checkedFiles = data['checkedFiles']
    for filename in checkedFiles:
        fileinfo = checkedFiles[filename]
        check = fileinfo.get('check', None)
        force = fileinfo.get('force', False)
        if not osp.exists(filename) or (force and check != fileHash(filename)):
            fileURL = urlparse.urljoin(siteURL, filename)
            print 'fetching', filename
            if not fetchFile(fileURL, filename, check):
                print 'fetching files failed'
                return -1
            else:
                count += 1

    return count

def fetch(site = Site + 'media/',
          name = 'downloads.json'):

    r = fetchAllFiles(site, name)
    if r == 0:
        print 'You have all the files that have been released.'
    elif r > 0:
        print 'Fetched %d files' % r
        print 'Now go back to your Dashboard tab to see any new notebooks.'
    else:
        print 'Something went wrong, please post a question on Piazza'

#############################
#
# functions for submitting assignments
#
#############################

def pushNotebook(name, uuid,
        url = 'upload/upload.cgi'):
    '''Upload the notebook to our server'''

    if not name.endswith('.ipynb'):
        fname = name + '.ipynb'
    else:
        fname = name
    try:
        book = file(fname, 'rb').read()
    except IOError:
        raise UserWarning('Notebook %s not found.' % fname)
    check = fileHash(fname)
    try:
        assignment = expected['_assignment']
        score = expected['_score']
    except KeyError:
        raise UserWarning('You must run every cell in your notebook before submitting it.')

    data = {
        'name': name,
        'book': book,
        'uuid': uuid,
        'assignment': assignment,
        'score': score,
        'check': check
    }

    postdata = urllib.urlencode(data)
    # try to post it to the server
    for i in range(10):
        resp = urllib.urlopen(Site + url, postdata)
        if resp.getcode() == 200:
            break
        time.sleep(0.1 * i)
    else:
        code = resp.getcode()
        msg = resp.read()
        raise UserWarning('upload failed code=%s msg="%s"' % (code, msg))

    print resp.read()

def showSubmitButton():
    '''Generate code to diplay the submit button in the notebook'''
    import IPython.display as ipd

    html = '''
<p>Click the button below to submit your assignment. Watch for a confirmation message
that your notebook was successfully uploaded. You may submit as often as you wish,
only the last submission will count.</p>
<p id="errorHelp116" style="display:none; color:red">
Your submission failed. Make sure you run every cell in your notebook before trying to
submit it.</p>
<button id="submitButton116">Submit this notebook</button>
<p id="submitResponse116"></p>
<iframe id="loginResponse116" height="200" width="600"></iframe>
<script>
(function() {
    function submit_notebook() {
        var notebook = IPython.notebook.notebook_name,
            uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
                return v.toString(16);
            }),
            command = "comp521.pushNotebook('" + notebook + "', '" + uuid + "')",
            kernel = IPython.notebook.kernel,
            $sresp = $('#submitResponse116'),
            $def = $.Deferred(),
            handler = function (out) {
                console.log(out);
                if (out.content.status == "ok") {
                    $def.resolve("Tranfer OK");
                } else if(out.content.status == "error") {
                    $def.reject(out.content.ename + ": " + out.content.evalue);
                } else { // if output is something we haven't thought of
                    $def.reject("[out type not implemented]")
                }
            };
        $def.done(function(msg) {
            console.log('done', msg, notebook);
            $sresp.html(msg);
            claim_url = '%s'
                + 'upload/check/claim.cgi?nb='
                + encodeURI(notebook)
                + "&uuid="
                + uuid;
            console.log('claim_url', claim_url);
            $('#loginResponse116').attr('src', claim_url);
        });
        $def.fail(function(msg) {
            $sresp.html(msg);
            $('#errorHelp116').show();
        });
        // wait until save is complete before pushing the notebook
        $([IPython.events]).one('notebook_saved.Notebook', function() {
            kernel.execute(command, {shell: { reply: handler }});
        });
        $sresp.html('');
        IPython.notebook.save_notebook();
    }
    $('#submitButton116').click(submit_notebook);
})();
</script>
    ''' % Site
    return ipd.HTML(html)

##################################################
#
# functions for checking student answers
#
##################################################

# contains the expected answers
expected = {}

#Checker
def report(author, extra):
    '''Summarize the student's performance'''
    expected['_score'] = 0.0
    correct = 0
    problems = 0
    answered = 0
    choice = 0
    choice_points = 0
    total_choice_points = 0
    points = 0
    max_points = 0
    for tag in sorted(expected.keys()):
        if tag.startswith('_'):
            continue
        print tag
        problems += 1
        c = expected[tag]['correct']

        if c > 0:
            correct += c
            points += expected[tag]['points'] * c
            if c < 1:
                print tag, 'partially incorrect'
        else:
            print tag, 'incorrect'
        max_points += expected[tag]['points']
    if '_author' in expected and author == expected['_author']:
        print 'You must fill in your onyen into the author variable at the top of the script'
        return
    if '_collaborators' in expected and extra == expected['_collaborators']:
        print 'You must fill in the collaborators variable'
        return
    print "Report for", author
    print "  Collaborators:", extra
    if total_choice_points > 0:
        print "  %d of %d answered for up to %d points" % (answered, choice, choice_points)
    print "  %d of %d correct, %d of %d points" % (correct, problems-choice,
        points, max_points-total_choice_points)
    expected['_score'] = points
    return showSubmitButton()
#_Checker

def check_float(tag, given, ev, extra):
    '''Compare floats for approximate equality'''
    rtol = extra.get('relative_tolerance', 1e-5)
    atol = extra.get('absolute_tolerance', 1e-8)
    if not isinstance(given, (float, int)):
        print tag, 'incorrect type'
        #Helpful
        print ' expected float'
        #_Helpful
        return 0.0
    OK = abs(given - ev) < atol
    if not OK:
        print tag, 'incorrect'
        #Helpful
        print '  expected', ev
        #_Helpful
    return float(OK)

def check_relation(tag, value, ev, extra):
    '''Compare Dee Relations'''
    if not isinstance(value, Dee.Relation):
        print tag, 'incorrect type'
        #Helpful
        print 'expected Dee.Relation'
        #_Helpful
        return 0.0
    OK = value == ev
    if not OK:
        print tag, 'incorrect'
        #Helpful
        print 'expected', ev
        #_Helpful
    return float(OK)

def check_choice(tag, value, ev, extra):
    choice = extra['choice']

    if not isinstance(value, (str, unicode)):
        print tag, 'answer should be string'
        return 0

    # check it
    right = 0
    wrong = 0
    omitted = 0
    for c in value.upper():
        if c in ev:
            right += 1
        else:
            wrong += 1
    if len(ev) > len(value):
        omitted += len(ev) - len(value)

    # compute partial score here
    score = (right - wrong) / (right - omitted)

def listit(t):
    '''convert nested list,tuples into nested lists'''

    return list(map(listit, t)) if isinstance(t, (list, tuple)) else t

#Checker
def check(tag, value, **kwargs):
    '''Provide feedback on a single value'''
    assert tag in expected
    e = expected[tag]
    ev = e['value']
    extra = e['extra']
    score = 1.0
    message = 'correct'

    if gotDee and isinstance(ev, Dee.Relation):
        score = check_relation(tag, value, ev, extra)

    elif 'choice' in extra:
        score = check_choice(tag, value, ev, extra)
        if score == 0:
            message = 'not answered'
        else:
            message = 'answered'

    elif (isinstance(ev, (list, tuple)) and
          isinstance(value, (list, tuple)) and
          sorted(listit(ev)) == sorted(listit(value))):
        pass

    elif isinstance(ev, float):
        score = check_float(tag, value, ev, extra)

    elif value == ev:
        pass

    else:
        print tag, 'incorrect'
        #Helpful
        print '  expected', ev
        #_Helpful
        score = 0.0

    if score == 1.0:
        print tag, message
    elif score > 0:
        print tag, 'partially correct'

    e['correct'] = score
    check.expected = ev
#_Checker

def pickleName(assignment):
    '''Create the name of the expected answers pickle file from the assignment name'''
    return assignment + '.pickle'

#Checker
def start(assignment):
    '''Initialize expected values for checking a student submission'''
    expected.update(pickle.load(file(pickleName(assignment), 'rb')))
    return check, report
#_Checker
