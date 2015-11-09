
import logging
from math import ceil
import threading
from collections import deque
from datetime import datetime, timedelta
import requests


class Schedule():

    def __init__(self, goal, buffer_size):
        """
        Schedule holds the frequency and buffer size
        :param goal: how many updates must be reached, until update is stored
        :param buffer_size: how many entries should be stored
        """
        self.buffer = deque(maxlen=buffer_size)
        self.goal = goal
        self.count = goal - 1  # this will lead to an append on first update

    def update(self, currentState):
        self.count += 1
        if self.count == self.goal:
            self.count = 0  # reset count
            self.buffer.append(currentState)


class StateBuffer():

    def __init__(self, fetchFrequencySeconds):
        """
        Create state buffer.
        """
        if fetchFrequencySeconds > 60 or fetchFrequencySeconds < 0:
            raise Exception("Frequency must be between 0 and 60")
        self.fetchFrequencySeconds = fetchFrequencySeconds
        self.schedules = {
            "minute": Schedule(1, ceil(60 / fetchFrequencySeconds)),  # every fetch for one minute
            "hour": Schedule(ceil(60 / fetchFrequencySeconds), 60),  # per minute for one hour
            # "day": Schedule(ceil(60 * 60 / fetchFrequencySeconds), 24)  # per hour for one day
        }
        self.timestamp = datetime.now()
        self.last = None

    def _fetch_state_(self):
        """
        Fetch the current state from current leader.
        :return: the state of the current leader
        """
        try:
            # TODO(cmaloney): Access the mesos master redirect before requesting
            # state-summary so that we always get the "authoritative"
            # state-summary. leader.mesos isn't updated instantly.
            # That requires mesos stop returning hostnames from `/master/redirect`.
            # See: https://github.com/apache/mesos/blob/master/src/master/http.cpp#L746
            url = "http://leader.mesos/state-summary"
            logging.info("Get state from leading master %s" % url)
            resp = requests.get(url)
            if (resp.response_code != 200):
                raise Exception("Could not read from %s" % url)
            return resp.text
        except Exception as e:
            logging.warning("Could not fetch state: %s" % e)
            return "{}"

    def _update_(self, current):
        """
        Update all schedules with current state.json
        :param current: the current state to populate buffers.
        """
        self.last = current
        for schedule in self.schedules.values():
            schedule.update(current)

    def _increase_time_delta_(self):
        self.timestamp += timedelta(seconds=self.fetchFrequencySeconds)
        return self.timestamp

    def _schedule_(self):
        """
        This method will trigger itself periodically and will update all schedules.
        """
        self._increase_time_delta_()
        current = self._fetch_state_()
        self._update_(current)
        while self.timestamp < datetime.now():
            logging.info("Request took longer than interval frequency. Fast Forward.")
            self._update_(current)
            self._increase_time_delta_()
        threading.Timer(int((self.timestamp - datetime.now()).seconds), self._schedule_).start()

    def run(self):
        """
        Start the state buffer update
        """
        threading.Timer(0, self._schedule_).start()
