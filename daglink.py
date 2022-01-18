#!/usr/bin/env python3
import os, sys, re
import subprocess
import yaml
from optparse import OptionParser
from operator import methodcaller as method
import logging
import platform

def main():
	p = OptionParser(usage='%prog [options] [tag1 [tag2 [...]]]')
	p.add_option('-c', '--config', default=os.path.expanduser('~/.config/daglink/links.yml'), help="config YAML file (default=%default)")
	p.add_option('-f', '--force', action='store_true', help='Just do it, removing existing files, creating nonexistant directories, etc')
	p.add_option('-i', '--interactive', action='store_true', help='like --force, but ask')
	p.add_option('-t', '--tags', action='store_true', help='list all available tags')
	p.add_option('-v', '--verbose', action='store_const', dest='log_level', const=logging.DEBUG)
	p.add_option('-q', '--quiet', action='store_const', dest='log_level', const=logging.WARN)
	p.add_option('--info', action='store_const', dest='log_level', default=logging.INFO, const=logging.INFO, help='info log level (the default)')
	p.add_option('-n', '--dry-run', action='store_true', help='print all links that would be created')
	p.add_option('-r', '--report', action='store_true', help='run ls -l on all paths')
	p.add_option('--clean', action='store_true', help='clean all links that daglink has ever created')
	p.add_option('--quick', action='store_true', help='currently makes no difference')
	p.add_option('--sudo', help='sudo implementation (e.g sudo, pkexec, gksudo)', default=None)
	p.add_option('-b', '--base', help='base directory')
	opts, tags = p.parse_args()
	logging.basicConfig(level=opts.log_level, format="daglink: %(message)s")
	tags = set(tags)
	dag = DagLink(opts)
	conf = dag.load_file(opts.config)

	try:
		if opts.tags:
			tags = set()
			for dir, vals in sorted(dag.each_item(conf)):
				for directive in vals:
					if 'tags' in directive:
						tags.update(directive['tags'].split())
			print("\n".join(sorted(tags)))
		elif opts.clean:
			return dag.clean(conf)
		else:
			return dag.process(conf, tags=tags)
	finally:
		dag.close()

class Skipped(RuntimeError): pass

class KnownLinks(object):
	def __init__(self, path):
		try:
			self.file = open(path, 'r+')
		except IOError:
			base = os.path.dirname(path)
			if not os.path.isdir(base):
				os.makedirs(base)
			self.file = open(path, 'w')
			self.paths = set()
		else:
			self.paths = self._entries(self.file.readlines())
		self.orig_paths = self.paths.copy()
		logging.debug("loaded %s known paths" % (path,))
	
	def _entries(self, lines):
		stripped = map(method('strip'), lines)
		self.file.seek(0)
		return set(filter(None, stripped))

	def add(self, path):
		logging.debug("adding known path: %s" % (path,))
		self.paths.add(path)

	def remove(self, path):
		logging.debug("removing known path: %s" % (path,))
		try:
			self.paths.remove(path)
		except KeyError: pass
	
	def close(self):
		if self.orig_paths != self.paths:
			self.write()
		self.file.close()
		self.file = None
	
	def write(self):
		lines = sorted(self.paths)
		logging.debug("writing %s paths to known_links" % (len(self.paths),))
		print(('\n'.join(lines)), file=self.file)
	
	def __iter__(self):
		return iter(self.paths)

	def __len__(self):
		return len(self.paths)


class DagLink(object):
	ZEROINSTALL_ALIASES = 'zeroinstall_aliases'
	DEFAULT_TAGS = 'default_tags'
	BASEDIR = 'basedir'
	HOST_INFO = 'hosts'

	def __init__(self, opts):
		self.opts = opts
		self._known_links = None
	
	def close(self):
		if self._known_links is not None:
			self._known_links.close()
	
	@property
	def known_links(self):
		if self._known_links is None:
			path = os.path.expanduser('~/.config/daglink/known_links')
			self._known_links = KnownLinks(path)
		return self._known_links
	
	def load_file(self, filename):
		with open(filename) as conffile:
			return yaml.safe_load(conffile.read())

	def process_file(self, filename, tags):
		self.process(self.load_file(filename), tags)

	def each_item(self, conf):
		for path, values in sorted(conf.items()):
			if path.startswith('_'):
				continue
			if isinstance(values, dict):
				values = [values]
			yield path, values

	def _load_meta(self, conf, tags):
		"""load options defined in the config file itself"""
		meta = conf.pop('meta', {})
		aliases = meta.get(self.ZEROINSTALL_ALIASES, {})
		config_basedir = meta.get(self.BASEDIR, None)
		basedir = self.opts.base or config_basedir
		hostname = platform.node()

		host_info = meta.get(self.HOST_INFO, None)
		if host_info:
			found = None
			for name, details in host_info.items():
				regex = details.get('regex', None)
				if regex and re.match(regex, hostname):
					logging.debug("hostname (%s) matches regex (%s)", hostname, regex)
					found = details
					break

				if name and name == hostname:
					logging.debug("matched exact hostname %s", name)
					found = details
					break

			if found is not None:
				if len(tags) == 0:
					tags = set(found.get('tags', []))

		# DEPRECATED tags use (TODO: remove me)
		default_tags = meta.get(self.DEFAULT_TAGS, None)
		if default_tags:
			logging.warn("The default_tags meta section is deprecated. See https://github.com/gfxmonk/daglink/commit/0cd4b3188d3347d2275f0e6e56f954307a3f0ac3")
			if len(tags) == 0:
				tags = default_tags.get(hostname, [])

		logging.info("using tags: %s" % (" ".join(sorted(tags)),))

		if basedir:
			logging.debug("using basedir: %s" % (basedir,))
			# TODO: it's probably better to integrate basedir into file ops, instead of chdir
			self.opts.config = os.path.abspath(self.opts.config)
			os.chdir(os.path.expanduser(basedir))
		return (tags, aliases)

	def _is_daglinked(self, file):
		return file in self.known_links and os.path.islink(file)

	def _mark_daglinked(self, file):
		if self.opts.dry_run:
			return
		self.known_links.add(file)
	
	def clean(self, conf):
		skipped = set()
		for path in self._each_daglinked(conf, quick=self.opts.quick):
			try:
				self._remove(path)
			except Skipped:
				skipped.add(path)
				pass
		if skipped:
			logging.error("skipped %s paths:\n   %s" % (len(skipped),"\n   ".join(sorted(skipped))))
			return len(skipped)
	
	def _file_scan(self, conf, quick=None):
		for path, values in self.each_item(conf):
			yield self._abs(path)
		for path in self.known_links:
			yield self._abs(path)

	def each_applicable_directive(self, conf, tags):
		tags, aliases = self._load_meta(conf, tags)
		def resolve(value):
			return aliases.get(value, value)
		def resolve_directive(directive):
			try:
				directive['uri'] = resolve(directive['uri'])
			except KeyError: pass
			return directive

		def should_include_directive(directive):
			directive_tags = directive.get('tags', '').split()
			if not directive_tags:
				return True
			return set(directive_tags).issubset(tags)
		if '*' in tags:
			should_include_directive = lambda *a: True
		for path, values in self.each_item(conf):
			logging.debug("Processing path: %s" % (path,))

			all_tags = filter(None, map(lambda f: f.get('tags',None), values))
			values = filter(should_include_directive, values)
			if not values:
				logging.debug("no applicable directives found (you did not specify any tags in: %s)" % (
					" ".join(all_tags),))
				continue
			path = self._abs(path)
			yield path, map(resolve_directive, values)

	def _each_daglinked(self, conf, quick=None):
		seen = set()
		for path in self._file_scan(conf, quick=quick):
			if self._is_daglinked(path):
				if path in seen: continue
				seen.add(path)
				yield path

	def process(self, conf, tags):
		skipped = set()
		num_paths = 0

		old_links = set(self._each_daglinked(conf, quick=True))

		for path, values in self.each_applicable_directive(conf, tags):
			try: old_links.remove(path)
			except KeyError: pass

			num_paths += 1
			try:
				if self.opts.report:
					# path-level operation
					self._report(path)
					continue
				else:
					assert len(values) == 1, "\n - ".join(
								["Too many applicable directives for path %s:" % (path,)]
								+ list(map(repr, values))
					)
					directive = values[0]
					self._apply_directive(path, directive)
			except Skipped:
				skipped.add(path)
				pass
		for path in sorted(old_links):
			try:
				self._remove(path)
			except Skipped:
				skipped.add(path)
				pass
		logging.info("%s paths successfully processed" % (num_paths,))
		if skipped:
			logging.error("skipped %s paths:\n   %s" % (len(skipped),"\n   ".join(sorted(skipped))))
			return len(skipped)
		else:
			os.utime(self.opts.config, None)

	def _remove(self, path):
		if self.opts.dry_run:
			print("rm %s" % (path,))
			return
		self._run(['rm', path])
		self.known_links.remove(path)

	def _report(self, path):
		self._run(['ls','-ld', path], try_root=False)
	
	def _apply_directive(self, path, directive):
		local_path = directive.get('path', None)
		if local_path:
			target = local_path
		else:
			target = self._resolve_0install_path(directive['uri'], directive.get('extract', None))
			if target is None:
				logging.error("Can't update %s: it belongs to a package implementation", path)
				raise Skipped()
		target = self._abs(target)
		self._link(path, target, directive)
	
	def _resolve_0install_path(self, uri, extract=None):
		import zerofind
		#TODO: check for updates?
		path = zerofind.find(uri)
		if path is None:
			return path
		if extract:
			path = os.path.join(path, *extract.split('/'))
		return path

	def _abs(self, path):
		return os.path.abspath(os.path.expanduser(path))

	def _link(self, path, target, directive):
		basedir = os.path.dirname(path)
		if not os.path.exists(basedir):
			self._permission('make directory at path %s' % (basedir,))
			self._run(['mkdir', '-p', basedir])
		if not os.path.exists(target):
			assert directive.get('optional', False) is True, "ERROR: non-existant target: %s\n (add `optional: true` to this entry if it can be skipped)" % (target,)
			logging.warn("Linking to missing target %s" % (target,))
		try:
			if os.path.islink(path):
				current_dest = os.readlink(path)
				if current_dest == target:
					logging.debug("link at %s already points to %s; nothing to do..." % (path, target))
					return
				logging.debug("link at %s points to %s; changing to %s", path, current_dest, target)
				self._run(['rm', path])
			elif os.path.exists(path):
				self._permission('remove existing contents at %s' % (path,))
				self._run(['rm', '-rf', path])
			self._run(['ln', '-s', target, path])
		finally:
			self._mark_daglinked(path)
	
	def _permission(self, msg):
		if self.opts.dry_run:
			print("(permission required: %s)" % (msg,))
			return
		if self.opts.force:
			return
		if self.opts.interactive:
			if self._prompt(msg):
				return
		else:
			logging.error('Skipped; use --force or --interactive to %s' % (msg,))
		raise Skipped(msg)
	
	def _prompt(self, msg):
		if not self.opts.interactive:
			return False
		print(msg + "? [Y/n] ", file=sys.stderr, end='')
		return raw_input().strip().lower() in ('','y','yes','ok')

	def _run(self, cmd, try_root=True):
		cmd = list(cmd)
		if self.opts.dry_run:
			print(" + %s" % (" ".join(cmd)))
			return
		try:
			subprocess.check_call(cmd, stderr=open(os.devnull))
		except subprocess.CalledProcessError:
			if try_root:
				self._permission('run "%s" as root' % (' '.join(cmd),))
				subprocess.check_call(self._sudo_cmd() + cmd)
			else:
				raise Skipped()

	def _sudo_cmd(self):
		if self.opts.sudo:
			return self.opts.sudo.split()
		else:
			return self._graphical_sudo()
	
	def _graphical_sudo(self):
		from whichcraft import which
		if which('pkexec'):
			return ['pkexec']
		elif which('gksudo'):
			return ['gksudo', '--']
		return ['sudo', '--']


if __name__ == '__main__':
	try:
		sys.exit(main())
	except AssertionError as e:
		print("%s: %s" % (type(e).__name__, e), file=sys.stderr)
		sys.exit(1)
	except KeyboardInterrupt:
		sys.exit(1)
