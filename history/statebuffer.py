
import logging
import threading
import requests
from urllib.parse import urljoin

from collections import deque


class StateBuffer():

    def __init__(self, urls, buffer_count=60, interval_seconds=60):
        """
        Create state buffer
        :param urls: the list of all master urls
        :param buffer_count: the number of state items to buffer
        :param interval_seconds: the interval to fetch the state
        :return:
        """
        self.urls = urls
        self.intervalSeconds = interval_seconds
        self.entries = deque(maxlen=buffer_count)

    def _find_leader_(self):
        """
        Find the leading master from the list of known masters
        :return: url of the leading master
        """
        for url in self.urls:
            try:
                redirect = requests.get(urljoin(url, "/master/redirect"), allow_redirects=False)
                if redirect.status_code == 307:
                    return redirect.headers['Location']
            except Exception as e:
                logging.warn("could not access %s since %s" % (url, e))
        return None

    def _fetch_state_(self):
        """
        Fetch the current state from current leader.
        :return: the state of the current leader
        """
        try:
            url = self._find_leader_()
            logging.info("Get state from leading master %s" % url)
            resp = requests.get(urljoin(url, "/state.json"), stream=False)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logging.warn("Could not fetch state: %s" % e)
            return "{}"

    def _update_(self):
        """
        Get latest entry and add to circular buffer.
        This method will get triggered periodically.
        """
        current = self._fetch_state_()
        self.entries.append(current)
        threading.Timer(self.intervalSeconds, self._update_).start()

    def run(self):
        """
        Start the state buffer update
        :return:
        """
        threading.Timer(1, self._update_).start()
