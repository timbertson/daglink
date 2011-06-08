# daglink
..because trees are boring

### Why would you need this?

 - You have customised a lot of files in your system
 - you want to keep them in a central location, in order to:
    - back them up easily
    - keep track of them
    - (maybe) version control them
 - you want to link different things into different (or the same) locations depending on hostname
    - e.g link a different /etc/apt.sources.list depending on distribution version
 - you want a tool that is so meta, it can install itself


## Configuration:

All the configuration is in one file, that is by default searched for in `~/.config/daglink/links.yml`. But you can use `-c` to provide your own config path.

The basic entry looks like this:

    /etc/path/to/wherever:
      path: ~/config/whatever-config

This will link `/etc/path/to/wherever` to `~/config/whatever-config`. You can use relative paths as the `path` value, they are taken from the current directory (or from the `--base` option).

If you love zero-install (I do), you can use daglink to make sure a location contains the latest version of a given feed. For example, you can add daglink itself to run whenever you login with this rather self-referential entry:

    ~/.config/autostart/daglink-update.desktop:
      uri: http://gfxmonk.net/dist/0install/daglink.xml
      extract: daglink-update.desktop

The beauty of this is that if you have a development version of daglink registered for that interface it will be used, otherwise it'll be cached from the internet and updated periodically, just like any other zero install feed. There aren't many cases where it's a good idea to keep symlinks of 0install implementations around, but I think symlinks to desktop items can be quite useful - especially if you want to take this configuration to a new machine.

## Meta:

You can provide more than just paths in the configuration.

(todo: finish documentation...)
