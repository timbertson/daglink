#!/usr/bin/env python
import os, sys
import subprocess
import yaml
from optparse import OptionParser
import logging

def main():
	p = OptionParser(usage='%prog [options] [tag1 [tag2 [...]]]')
	p.add_option('-c', '--config', default=os.path.expanduser('~/.config/daglink/conf'))
	p.add_option('-f', '--force', action='store_true', help='Just do it, removing existing files, creating nonexistant directories, etc')
	p.add_option('-i', '--interactive', action='store_true', help='like --force, but ask')
	p.add_option('-t', '--tags', action='store_true', help='list all available tags')
	p.add_option('-v', '--verbose', action='store_const', dest='log_level', const=logging.DEBUG, help='verbose')
	p.add_option('-q', '--quiet', action='store_const', dest='log_level', const=logging.WARN, help='verbose')
	p.add_option('--info', action='store_const', dest='log_level', default=logging.INFO, const=logging.INFO, help='verbose')
	p.add_option('-n', '--dry-run', action='store_true', help='print all links that would be created')
	p.add_option('-r', '--report', action='store_true', help='run ls -l on all paths')
	p.add_option('-b', '--base', help='base directory')
	opts, tags = p.parse_args()
	logging.basicConfig(level=opts.log_level, format="%(message)s")
	tags = set(tags)
	dag = DagLink(opts)
	conf = dag.load_file(opts.config)
	if opts.base:
		os.chdir(os.path.expanduser(opts.base))
	if opts.tags:
		tags = set()
		for dir, vals in dag.each_item(conf):
			for directive in vals:
				if 'tags' in directive:
					tags.update(directive['tags'].split())
		print "\n".join(sorted(tags))
	else:
		return dag.process(conf, tags=tags)

class Skipped(RuntimeError): pass

class DagLink(object):
	ZEROINSTALL_ALIASES = 'zeroinstall_aliases'
	DEFAULT_TAG = '__default__'
	def __init__(self, opts):
		self.opts = opts
	
	def load_file(self, filename):
		with open(filename) as conffile:
			return yaml.load(conffile.read())

	def process_file(self, filename, tags):
		self.process(self.load_file(filename), tags)

	def each_item(self, conf):
		for path, values in conf.items():
			if isinstance(values, dict):
				values = [values]
			yield path, values

	def process(self, conf, tags):
		skipped = 0
		aliases = conf.pop(self.ZEROINSTALL_ALIASES, {})
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
			if self.opts.report:
				self._report(path)
				continue
			assert len(values) == 1, "Too many applicable directives for path %s:\n%s" % (
					path,
					"\n".join(map(repr, values)))
			directive = values[0]

			path = os.path.expanduser(path)
			try:
				self._apply_directive(path, directive, resolve)
			except Skipped:
				skipped += 1
				pass
		if skipped:
			logging.error("skipped %s directives" % (skipped,))
			return skipped

	def _report(self, path):
		self._run(['ls','-l',path], try_root=False)

	def _apply_directive(self, path, directive, resolve):
		local_path = directive.get('path', None)
		if local_path:
			target = os.path.abspath(os.path.realpath(local_path))
		else:
			target = self._resolve_0install_path(resolve(directive['uri']), directive.get('extract', None))
		self._link(path, target)
	
	def _resolve_0install_path(self, uri, extract=None):
		import zerofind
		path = zerofind.find(uri)
		assert path
		if extract:
			path = os.path.join(path, *extract.split('/'))
		return path

	def _link(self, path, target):
		target = os.path.abspath(os.path.expanduser(target))
		if self.opts.dry_run:
			print "%s -> %s" % (path, target)
			return
		basedir = os.path.dirname(path)
		if not os.path.exists(basedir):
			self._permission('make directories to %s' % (basedir,))
			self._run(['mkdir', '-p', basedir])
		assert os.path.exists(target), "ERROR: non-existant target: %s" % (path,)
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
				subprocess.check_call(['sudo'] + cmd)
			else:
				raise Skipped()

if __name__ == '__main__':
	try:
		sys.exit(main())
	except AssertionError, e:
		print >> sys.stderr, e
		sys.exit(1)
	except KeyboardInterrupt:
		sys.exit(1)
