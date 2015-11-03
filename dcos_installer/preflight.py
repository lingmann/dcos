import ansible.runner
from ansible.playbook import PlayBook
import ansible.inventory 
from ansible import callbacks
from ansible import utils

import logging as log
import sys
import yaml
from jinja2 import Template
from tempfile import NamedTemporaryFile
import pprint


class LoggingCallbacks(callbacks.PlaybookCallbacks):
    def log(self, level, msg, *args, **kwargs):
        log.log(level, msg, *args, **kwargs)

    def on_task_start(self, name, is_conditional):
        self.log(log.INFO, 'task: {0}'.format(name))
        super(LoggingCallbacks, self).on_task_start(name, is_conditional)


class LoggingRunnerCallbacks(callbacks.PlaybookRunnerCallbacks):
    def log(self, level, msg, *args, **kwargs):
        log.log(level, msg, *args, **kwargs)

    def _on_any(self, level, label, host, orig_result):
        result = orig_result.copy()
        result.pop('invocation', None)
        result.pop('verbose_always', True)
        item = result.pop('item', None)
        if not result:
            msg = ''
        elif len(result) == 1:
            msg = ' | {0}'.format(result.values().pop())
        else:
            msg = '\n' + pprint.pformat(result)
        if item:
            self.log(level, '{0} (item={1}): {2}{3}'.format(host, item, label, msg))
        else:
            self.log(level, '{0}: {1}{2}'.format(host, label, msg))

    def on_failed(self, host, res, ignore_errors=False):
        if ignore_errors:
            level = log.INFO
            label = 'FAILED (ignored)'
        else:
            level = log.ERROR
            label = 'FAILED'
        self._on_any(level, label, host, res)
        super(LoggingRunnerCallbacks, self).on_failed(host, res, ignore_errors)

    def on_ok(self, host, res):
          self._on_any(log.INFO, 'SUCCESS', host, res)
          super(LoggingRunnerCallbacks, self).on_ok(host, res)

    def on_error(self, host, msg):
        self.log(log.ERROR, '{0}: ERROR | {1}'.format(host, msg))
        super(LoggingRunnerCallbacks, self).on_error(host, msg)

    def on_skipped(self, host, item=None):
        if item:
            self.log(log.INFO, '{0} (item={1}): SKIPPED'.format(host, item))
        else:
            self.log(log.INFO, '{0}: SKIPPED'.format(host))
        super(LoggingRunnerCallbacks, self).on_skipped(host, item)

    def on_unreachable(self, host, res):
        self._on_any(log.ERROR, 'UNREACHABLE', host, dict(unreachable=res))
        super(LoggingRunnerCallbacks, self).on_unreachable(host, res)

    def on_no_hosts(self):
        self.log(log.ERROR, 'No hosts matched')
        super(LoggingRunnerCallbacks, self).on_no_hosts()


def create_playbook(options):
    """
    Dynamically generate the ansible playbook for our roles.
    """
    ansible_playbook = """
- hosts:
    - master
    - slave_public
    - slave_private
  tasks:
    - name: preflight
      command: uptime
"""
    log.debug("Generating playbook...")
    print(ansible_playbook)
    with open(options.playbook_path, 'w') as f:
          f.write(ansible_playbook)


def uptime(options):
    """
    A foo def for testing ansible.
    """
    create_playbook(options)
    utils.VERBOSITY = 4 
    playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    stats = callbacks.AggregateStats()
    runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)
    
    # Can implement custom callbacks to handle logging:
    #stats = callbacks.AggregateStats()
    #playbook_cb = LoggingCallbacks(verbose=3)
    #runner_cb = LoggingRunnerCallbacks(stats, verbose=3)

    ssh_user = open(options.ssh_user_path, 'r').read()
    inventory = get_inventory(options.hosts_yaml_path)
    for role, hosts in inventory.iteritems():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory template for %s role with hosts %s", role, hosts)
            # HACK ATTACK: inventory file must be present even if I pass a list of hosts, so....
            inventory = """
            [{{ role }}]
            {{hosts}}
            """
            inventory_template = Template(inventory)
            rendered_inventory = inventory_template.render(
                role=role,
                hosts=hosts)
    
            print(rendered_inventory)
            hosts = NamedTemporaryFile(delete=False)
            hosts.write(rendered_inventory)
            hosts.close()

            log.info("Executing preflight on %s role...", role)
            pb = PlayBook(
                playbook=options.playbook_path,
                host_list=hosts.name,     
                remote_user=ssh_user,
                callbacks=playbook_cb,
                runner_callbacks=runner_cb,
                stats=stats,
                private_key_file=options.ssh_key_path
            )
            results = pb.run()
            playbook_cb.on_stats(pb.stats)

            log.info(results)
            dump_host_results(options, results)

        else:
            log.warn("%s is empty, skipping.", role)

    

def get_inventory(path):
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    #inventory = ansible.inventory.Inventory(hosts)
    return hosts

def dump_host_results(options, results):
    with open(options.preflight_results_path, 'a') as preflight_file:
        preflight_file.write(yaml.dump(results, default_flow_style=False))
