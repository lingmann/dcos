# Ideas

### Outputs

1. SSH Deploy
  - git it the priv ssh key 
  - ssh -c install slave ...
2. Expose Bootstrap URL
  - Integrates with CM systems like puppet, chef..
  - ex puppet site:

```ruby
node my.slave.com {
  class { ::dcos:
    bootstrap_url => 'my.bootstrap.com',
    role          => 'slave_public'
  }
}
...
```
3. Generate RPM/Deb
  - Generate an RPM or Deb of installation files
  - Integrates with places that are locked down - no CM, no remote server pulls
4. Download Tarball
  - Just give me the tarball

### Pipeline
Parts marked ALPHA are slated in the first release of the web installer:

1. Configurator - ALPHA
  - Config file input
2. Get IP Addresses - one choice of:
  - Get list of masters / slave_public / slave_private in console - ALPHA
  - Upload JSON: - ALPHA
TODO - review yaml functional version of this - consistency.

```json
{
  "masters": [],
  "slave_public": [],
  "slave_private": [],
}
```
3. Get ip-detect script - one choice of: - ALPHA
  - Use our ip-detect script (we have 3-5 that we ship)
    - Given subnet we can determine interface
    - Given OS version we have command..
  - Upload a custom one - ALPHA
4. Deploy - select deployment method, one of: ALPHA
  - SSH Deploy ALPHA
  - Bootstrap URL ALPHA
  - Download tarball ALPHA

If deployment method == 'SSH Deploy'

1. Preflight checks ALPHA
  1. Is machine up ALPHA
  1. Is it passing --preflight (run install script with flag only) ALPHA
  1. Is it returning ip address for ip-detect
  1. Returns list of nodes and their preflight status. If any return 1, we flag them.
1. Deploy
  1. SSH in parallel to 10 nodes at a time and run the installer. 


### Deploy SSH
Deploys via SSH over Fabric.

1. Present user with a view that ingests list for master ips, slave_public ips, slave_private ips with an optional "upload json".

Configures JSON, example:

```json
{
  "masters": [],
  "slave_public": [],
  "slave_private": [],
}
```


