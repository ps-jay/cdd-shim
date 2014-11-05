#!/bin/env python

import argparse
import os
import requests
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class CDDShim(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        # "Globals"
        self.IPUPGRADE = ['151.22.100.235']
        self.IPPORTAL = [
            '63.236.63.180',    # ABB AuroraVision
            '220.128.69.225',   # BenQ Solar
        ]
        self.PATHS = {
            '/dl_update_cdd.php': self.IPUPGRADE,
            '/dl_update_file_cdd.php': self.IPUPGRADE,
            '/dl_parameters_file.php': self.IPPORTAL,
        }
        self.ARGS = server.cmd_args

        # BaseHTTPRequestHandler isn't new-style, super() fails
        # super(CDDShim, self).__init__(request, client_address, server)
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def stamp_and_print(self, message):
        print "%s %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            message,
        )

    def debug(self, message):
        if self.ARGS.debug:
            self.stamp_and_print("DEBUG: %s" % message)

    def info(self, message):
        self.stamp_and_print("INFO: %s" % message)

    def warning (self, message):
        self.stamp_and_print("WARNING: %s" % message)

    def error(self, message):
        self.stamp_and_print("ERROR: %s" % message)

    def fatal(self, message):
        self.stamp_and_print("FATAL: %s" % message)

    def write_to_file(self, data, path):
        if self.ARGS.output is not None:
            normpath = os.path.normpath("%s%s" % (self.ARGS.output, path))
            if not normpath.startswith(self.ARGS.output):
                self.warning("URL path received: '%s' - attempted to break out of path '%s'; denied" % (
                    path,
                    self.ARGS.output,
                ))
            else:
                with open(normpath.strip(), 'wb') as fh:
                    fh.write(data)

    def send_data_to_servers(self, headers, data, servers, path):
        results = {}

        for server in servers:
            self.debug("Sending to %s" % server)

            try:
                r = requests.post(
                    'http://%s%s' % (
                        server,
                        path,
                    ),
                    data=data,
                    headers=headers,
                    timeout=55,
                )

                text = r.text
                status = r.status_code

                if str(status) not in results:
                    results[str(status)] = {}

                results[str(status)][server] = {
                    'text': text,
                    'status_code': status,
                    'headers': r.headers,
                }

                self.write_to_file(text, "/%s_%s--%d" % (
                    server,
                    path.replace("/", "_"),
                    status,
                ))

                if status == requests.codes.ok:
                    self.info("Forwarded %s to %s successfully" % (
                        path,
                        server,
                    ))
                else:
                    r.raise_for_status()

            except Exception, e:
                self.error("Exception occurred when forwarding %s to %s: %s" % (
                    path,
                    server,
                    str(e),
                ))

        return results

    def do_POST(self):
        if 'content-length' not in self.headers:
            self.error("content-length header not found in POST, aborting. (path: %s)" % self.path)
            self.send_response(requests.codes.precondition)
            return

        length = int(self.headers['content-length'])
        data = self.rfile.read(length)

        self.debug("POST received: %s (%d bytes)" % (
            self.path,
            length,
        ))
        
        self.write_to_file(data.decode(), self.path)

        code = requests.codes.server_error
        results = None

        if self.path in self.PATHS:
            self.info("Path '%s' received, %d servers to forward to: %s" % (
                self.path,
                len(self.PATHS[self.path]),
                ', '.join(self.PATHS[self.path]),
            ))
            results = self.send_data_to_servers(self.headers, data, self.PATHS[self.path], self.path)
            self.debug("Results: %s" % results)

        else:
            self.warning("Path '%s' received, but no configured action available" %
                self.path
            )
            code = requests.codes.not_found
            self.send_response(code)
            return

        if results is not None:
            if results == {}:
                self.send_response(code)
                return

            if str(requests.codes.ok) in results:
                code = requests.codes.ok
            else:
                # No 200's, use anything else
                for sc in results:
                    code = int(sc)
                    break

            # Use the first result & return it to the client
            self.send_response(code)
            for res in results[str(code)]:
                r = results[str(code)][res]
                for header in r['headers']:
                    # Python has already sent these two, skip them
                    if (header.lower() == 'server' or \
                        header.lower() == 'date'):
                        continue
                    self.send_header(header, r['headers'][header])
                self.end_headers()
                self.wfile.write(r['text'])

    def do_GET(self):
        self.error("Received a %s request at path %s - unsupported" % (
            self.command,
            self.path,
        ))
        self.send_response(requests.codes.not_implemented)

    def do_PUT(self):
        self.do_GET()

    def do_HEAD(self):
        self.do_GET()

    def do_CONNECT(self):
        self.do_GET()


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("-d", "--debug",
        help="Output debugging messages",
        action="store_true",
        default=False,
    )
    parser.add_argument("-b", "--bind-ip",
        help="Bind to a specific IP address",
        type=str,
        default=None,
    )
    parser.add_argument("-p", "--port",
        help="TCP port number to listen on",
        type=int,
        default=8080,
    )
    parser.add_argument("-o", "--output",
        help="Path to output files to",
        type=str,
        default=None,
    )

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    ip = args.bind_ip
    if ip is None:
        ip = ''
    server = HTTPServer((ip, args.port), CDDShim)
    server.cmd_args = args
    server.serve_forever()
