__author__ = 'Boboman'
import sys
import getopt
import time
import os
import json
import ConfigParser

import requests

from requests_toolbelt import MultipartEncoder

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class OctoPrint:
    def __init__(self, autoprint=False, select=False, apikey=None, host='127.0.0.1'):
        self.autoprint = autoprint
        self.select = select
        self.apikey = apikey
        self.host = host

    def home_xyz(self):
        headers = {'content-type': 'application/json', 'X-Api-Key': self.apikey}
        payload = {'command': 'home', 'axes': ["x", "y", "z"]}
        url = 'http://' + self.host + '/printer/printhead'

        r = requests.post(url, data=json.dumps(payload), headers=headers)

        if r.status_code == 204:
            print "Printer is homing the X,Y,Z axes ..."
        elif r.status_code == 400:
            print "Critical Error: Bad Request"
        elif r.status_code == 409:
            print "The printer is either already printing or not operational."

    def upload_file(self, filepath, filename):
        url = 'http://' + self.host + '/api/files/local'

        m = MultipartEncoder(
            fields={
                'file': (filename, open(filepath + "\\" + filename, 'rb'), 'application/octet-stream'),
                'select': str(self.select).lower(),
                'print': str(self.autoprint).lower()
            }
        )

        # m.content_type is required here as it will append the boundary token to the content type.
        headers = {'Content-Type': m.content_type, 'X-Api-Key': self.apikey}
        response = requests.post(url, data=m, headers=headers)

        response.raise_for_status()


class PrintOnCreateHandler(FileSystemEventHandler):
    def __init__(self, autoprint=False, select=False, host='127.0.0.1', apikey='asdf'):
        self.select = select
        self.host = host
        self.apikey = apikey
        self.autoprint = autoprint

    def on_created(self, event):
        # print 'Created File: ' + event.src_path
        filepath, filename = os.path.split(event.src_path)
        print 'Detected File change in ' + filepath + ' -- Uploading [' + filename + ']'

        octoprint = OctoPrint(autoprint=self.autoprint,
                              select=self.select,
                              apikey=self.apikey,
                              host=self.host)

        octoprint.upload_file(filepath, filename)

    def on_modified(self, event):
        print 'Modified File: ' + event.src_path


class Watcher:
    def __init__(self, autoprint=False, select=False, verbose=False, directories=None, recursive=False,
                 host='127.0.0.1', apikey=''):
        self.autoprint = autoprint
        self.select = select
        self.verbose = verbose
        self.directories = directories
        self.recursive = recursive
        self.observer = Observer()
        self.host = host
        self.apikey = apikey

    def start(self):
        if not self.directories:
            print 'There were no directories specified.'
            sys.exit(2)
        else:
            self.log('Initializing...')
            self.log('Watching directories: ' + str(self.directories))
            self.log('AutoPrint= ' + str(self.autoprint))
            self.log('AutoSelect=  ' + str(self.select))
            self.watch_directories(self.directories)

    def stop(self):
        self.observer.stop()

    def watch_directories(self, directories):
        event_handler = PrintOnCreateHandler(autoprint=self.autoprint, select=self.select, host=self.host,
                                             apikey=self.apikey)
        for the_path in directories:
            self.log('Adding watch on ' + the_path.strip())
            self.observer.schedule(event_handler, the_path.strip(), recursive=bool(self.recursive))

        self.log('Attempting to start the watch thread.')

        try:
            self.observer.start()
        except WindowsError:
            print 'ERROR: There were problems initializing the watcher thread.  Check that the directories exist.'

        if self.observer.isAlive():
            try:

                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.observer.stop()

            self.observer.join()

    def log(self, message):
        if self.verbose:
            print '<#Octonomous>  ' + message


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "asvrH:k:c:",
                                   ["auto-print", "select", "verbose", "recursive", "host=", "apikey=",
                                    "config=" "fart"])
    except getopt.GetoptError:
        print '\n\nOctonomous watches directories on the filesystem and uploads new files to an octoprint server.'
        print 'Octonomous takes advantage of the auto-print and auto-select flags.'
        print 'usage: Octonomous [OPTIONS...]  [FILEPATH1 FILEPATH2 ... FILEPATHN]'
        print 'Example: Octonomous -asvr  /home/boboman/gcode '
        print 'Example: Octonomous -c custom-config.cfg'
        print ''
        print 'Options:'
        print '-a, --auto-print    Automatically print uploaded files'
        print '-s, --select        Select this file, queueing it for the next print'
        print '-v, --verbose       Enable verbose output.'
        print '-r, --recursive     Recursively watch the directories'
        print '-c, --config-file   Specify a config file'
        print '-H, --host=<value>  Specify the address of the server'
        print '-k, --apikey=<value> Specify the apikey for the server\'s rest api'
        sys.exit(2)

    autoprint = False
    select = False
    verbose = False
    recursive = False
    host = None
    apikey = None
    directories = args

    for opt, arg in opts:
        if opt in ('-c', 'config='):
            print 'config arg= ' + arg
            config = ConfigParser.RawConfigParser()
            config.read(arg)

            host = config.get('octonomous', 'host')
            apikey = config.get('octonomous', 'apikey')

            select = 'true' == config.get('octonomous', 'select')
            autoprint = 'true' == config.get('octonomous', 'autoprint').lower()
            recursive = 'true' == config.get('octonomous', 'recursive').lower()
            verbose = 'true' == config.get('octonomous', 'verbose').lower()

            directories = [path for key, path in config.items("directories")]

        else:
            if opt in ('-a', '--auto-print'):
                autoprint = True
                # possibility of a confirm prompt as this could be dangerous(?)
            if opt in ('-s', '--select', '/s'):
                select = True
            if opt in ('-v', '--verbose', '/v'):
                verbose = True
            if opt in ('-r', '--recursive', '/r'):
                recursive = True
            if opt in ('-H', '--host', '/H'):
                host = arg
            if opt in ('-k', '--apikey', '/k'):
                apikey = arg
            if opt == '--fart':
                fart()

    print 'args= ' + str(args)

    watcher = Watcher(autoprint=autoprint, select=select, directories=directories, verbose=verbose, recursive=recursive,
                      apikey=apikey, host=host)
    watcher.start()


def fart():
    print '                                         ___    ,\'""""\'.'
    print '                                     ,"""   """"\'      `.'
    print '                                    ,\'        _.         `._'
    print '                                   ,\'       ,\'              `"""\'.'
    print '                                  ,\'    .-""`.    ,-\'            `.'
    print '                                 ,\'    (        ,\'                :'
    print '                               ,\'     ,\'           __,            `.'
    print '                         ,""""\'     .\' ;-.    ,  ,\'  \             `"""".'
    print '                       ,\'           `-(   `._(_,\'     )_                `.'
    print '                      ,\'         ,---. \ @ ;   \ @ _,\'                   `.'
    print '                 ,-""\'         ,\'      ,--\'-    `;\'                       `.'
    print '                ,\'            ,\'      (      `. ,\'                          `.'
    print '                ;            ,\'        \    _,\',\'                            `.'
    print '               ,\'            ;          `--\'  ,\'                              `.'
    print '              ,\'             ;          __    (                    ,           `.'
    print '              ;              `____...  `78b   `.                  ,\'           ,\''
    print '              ;    ...----\'\'\'\' )  _.-  .d8P    `.                ,\'    ,\'    ,\''
    print ' _....----\'\'\' \'.        _..--"_.-:.-\' .\'        `.             ,\'\'.   ,\' `--\''
    print '               `" mGk "" _.-\'\' .-\'`-.:..___...--\' `-._      ,-"\'   `-\''
    print '         _.--\'       _.-\'    .\'   .\' .\'               `"""""'
    print '   __.-\'\'        _.-\'     .-\'   .\'  /'
    print '  \'          _.-\' .-\'  .-\'        .\''
    print '         _.-\'  .-\'  .-\' .\'  .\'   /'
    print '     _.-\'      .-\'   .-\'  .\'   .\''
    print ' _.-\'       .-\'    .\'   .\'    /'
    print '        _.-\'    .-\'   .\'    .\''
    print '     .-\'            .\''


if __name__ == "__main__":
    main(sys.argv[1:])