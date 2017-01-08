# daglink
..because trees are boring

<img src="http://gfxmonk.net/dist/status/project/daglink.png">

### Why would you need this?

 - You have customised a lot of files in your system
 - you want to keep them in a central location, in order to:
    - back them up easily
    - keep track of them
    - (maybe) version control them
 - you want to link different things into different (or the same) locations depending on hostname
    - e.g link a different /etc/apt.sources.list depending on distribution version
 - you want a tool that is so meta, it can install itself

## What does it do?

daglink makes symbolic links. The main usage is linking various well-known paths to somewhere within a self-contained config directory. E.g. you can keep all your settings in ~/dev/config, and creates links to files / folders within it from e.g /etc/apt/sources.list.d, /etc/sessions.d, ~/.vimrc.

Really it can be used for any configuration that requires well-known paths and you wish to store the contents of such files in a place of your choosing.

## Configuration:

All the configuration is in one file, that is by default searched for in `~/.config/daglink/links.yml`. But you can use `-c` to provide your own config path.

The basic entry looks like this:

    /etc/path/to/wherever:
      path: ~/config/whatever-config

This will link `/etc/path/to/wherever` to `~/config/whatever-config`. You can use relative paths as the `path` value, they are taken from the current directory (or from the `--base` option).

### Tags:

You probably don't want to link the same things to the same places on every computer you use. For this, you can use tags. To specify that a directive only applies for a given tag, you can use:

    /etc/path/to/wherever:
      path: ~/config/whatever-config
      tags: home

(`tags` is a space-separated list, the directive will be applied if you have specified all of the given tags)

To specify multiple targets for a single location, use a list:

    /etc/path/to/wherever:
      - path: ~/config/home-config
        tags: home
      - path: ~/config/work-config
        tags: work

**Note**: this will fail if more than one directive matches the provided set of tags, as that would be impossible to do.

## Meta:

You can provide more than just paths in the configuration. There is a `meta` section which allows you to specify:

#### default basedir

If you don't specify --basedir, daglink will take the base directory form the meta section (if it exists):

    meta:
      basedir: ~/dev/config

#### default tags per-hostname

If you want to use daglink to update your symlinks automaically, you'll want to put per-machine tags in your config. These tags are only used if you don't specify any tags on the command line itself:

    meta:
      hosts:
        hostname_1:
          tags:
            - ubuntu-maverick
            - xmodmap
        fedora_hosts:
          regex: "fed.*"
          tags:
            - fedora-15
            - xkb

The `regex` value, if present, will take precedence over the default exact hostname matching.

For a complete example config, feel free to peek at my own configuration: <https://github.com/gfxmonk/app-customisations/blob/master/meta/links.yml>
