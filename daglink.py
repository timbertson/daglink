#!/usr/bin/env python
import os, sys
import subprocess
import yaml
from optparse import OptionParser
import logging

def main():
	p = OptionParser(usage='%prog [options] [tag1 [tag2 [...]]]')
	p.add_option('-c', '--config', default=os.path.expanduser('~/.config/daglink/links.yml'), help="config YAML file (default=%default)")
	p.add_option('-f', '--force', action='store_true', help='Just do it, removing existing files, creating nonexistant directories, etc')
	p.add_option('-i', '--interactive', action='store_true', help='like --force, but ask')
	p.add_option('-t', '--tags', action='store_true', help='list all available tags')
	p.add_option('-v', '--verbose', action='store_const', dest='log_level', const=logging.DEBUG, help='verbose')
	p.add_option('-q', '--quiet', action='store_const', dest='log_level', const=logging.WARN, help='verbose')
	p.add_option('--info', action='store_const', dest='log_level', default=logging.INFO, const=logging.INFO, help='verbose')
	p.add_option('-n', '--dry-run', action='store_true', help='print all links that would be created')
	p.add_option('-r', '--report', action='store_true', help='run ls -l on all paths')
	p.add_option('--remove', action='store_true', help='remove all files that have been linked')
	p.add_option('--sudo', help='sudo implementation (e.g sudo, pkexec, gksudo)', default=None)
	p.add_option('-b', '--base', help='base directory')
	opts, tags = p.parse_args()
	logging.basicConfig(level=opts.log_level, format="daglink: %(message)s")
	tags = set(tags)
	dag = DagLink(opts)
	conf = dag.load_file(opts.config)

	if opts.tags:
		tags = set()
		for dir, vals in sorted(dag.each_item(conf)):
			for directive in vals:
				if 'tags' in directive:
					tags.update(directive['tags'].split())
		print "\n".join(sorted(tags))
	else:
		return dag.process(conf, tags=tags)

class Skipped(RuntimeError): pass

class DagLink(object):
	ZEROINSTALL_ALIASES = 'zeroinstall_aliases'
	DEFAULT_TAGS = 'default_tags'
	BASEDIR = 'basedir'

	def __init__(self, opts):
		self.opts = opts
	
	def load_file(self, filename):
		with open(filename) as conffile:
			return yaml.load(conffile.read())

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

		default_tags = meta.get(self.DEFAULT_TAGS, None)
		if len(tags) == 0 and default_tags:
			import platform
			hostname = platform.node()
			hostname_tags = default_tags.get(hostname, None)
			if hostname_tags:
				tags = set(hostname_tags)
		logging.info("using tags: %s" % (" ".join(sorted(tags)),))

		if basedir:
			logging.debug("using basedir: %s" % (basedir,))
			os.chdir(os.path.expanduser(basedir))
		return (tags, aliases)

	def process(self, conf, tags):
		tags, aliases = self._load_meta(conf, tags)
		skipped = []
		num_paths = 0
		def resolve(value):
			return aliases.get(value, value)

		def should_include_directive(directive):
			directive_tags = directive.get('tags', '').split()
			if not directive_tags:
				return True
			return len(set(directive_tags).intersection(tags)) > 0

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
			num_paths += 1
			path = self._abs(path)

			try:
				if self.opts.report or self.opts.remove:
					# path-level operations
					if self.opts.report:
						self._report(path)
					elif self.opts.remove:
						self._remove(path)
					else:
						assert False, "invalid state!"
					continue
				else:
					assert len(values) == 1, "Too many applicable directives for path %s:\n%s" % (
							path,
							"\n".join(map(repr, values)))
					directive = values[0]
					self._apply_directive(path, directive, resolve)
			except Skipped:
				skipped.append(path)
				pass
		logging.info("%s paths successfully processed" % (num_paths,))
		if skipped:
			logging.error("skipped %s paths:\n   %s" % (len(skipped),"\n   ".join(skipped)))
			return len(skipped)
		else:
			os.utime(self.opts.config, None)

	def _remove(self, path):
		if self.opts.dry_run:
			print "rm %s" % (path,)
			return
		self._run(['rm', path])

	def _report(self, path):
		self._run(['ls','-l', path], try_root=False)

	def _apply_directive(self, path, directive, resolve):
		local_path = directive.get('path', None)
		if local_path:
			target = local_path
		else:
			target = self._resolve_0install_path(resolve(directive['uri']), directive.get('extract', None))
		target = self._abs(target)
		self._link(path, target)
	
	def _resolve_0install_path(self, uri, extract=None):
		import zerofind
		#TODO: check for updates?
		path = zerofind.find(uri)
		assert path
		if extract:
			path = os.path.join(path, *extract.split('/'))
		return path

	def _abs(self, path):
		return os.path.abspath(os.path.expanduser(path))

	def _link(self, path, target):
		if self.opts.dry_run:
			print "%s -> %s" % (path, target)
			return
		basedir = os.path.dirname(path)
		if not os.path.exists(basedir):
			self._permission('make directory at path %s' % (basedir,))
			self._run(['mkdir', '-p', basedir])
		assert os.path.exists(target), "ERROR: non-existant target: %s" % (target,)
		if os.path.islink(path):
			if os.readlink(path) == target:
				logging.debug("link at %s already points to %s; nothing to do..." % (path, target))
				return
			self._run(['rm', path])
		elif os.path.exists(path):
			self._permission('remove existing contents at %s' % (path,))
			self._run(['rm', '-rf', path])
		self._run(['ln', '-s', target, path])
	
	def _permission(self, msg):
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
		print >> sys.stderr, msg + "? [Y/n] ",
		return raw_input().strip().lower() in ('','y','yes','ok')

	def _run(self, cmd, try_root=True):
		cmd = list(cmd)
		try:
			subprocess.check_call(cmd, stderr=open(os.devnull))
		except subprocess.CalledProcessError:
			if try_root:
				self._permission('run "%s" as root' % (' '.join(cmd),))
				subprocess.check_call(self._sudo_cmd() + ['--'] + cmd)
			else:
				raise Skipped()

	def _sudo_cmd(self):
		if self.opts.sudo:
			return self.opts.sudo.split()
		else:
			return self._graphical_sudo()
	
	def _graphical_sudo(self):
		if os.system('which pkexec >/dev/null 2>&1') == 0:
			return ['pkexec']
		else:
			return ['gksudo']


if __name__ == '__main__':
	try:
		sys.exit(main())
	except AssertionError, e:
		print >> sys.stderr, e
		sys.exit(1)
	except KeyboardInterrupt:
		sys.exit(1)
