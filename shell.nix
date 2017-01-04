{ pkgs ? import <nixpkgs> {} }:
import ./nix/default.nix {
	inherit (pkgs) lib;
	pythonPackages = pkgs.python2Packages;
	fetchFromGitHub = _ignored: ./nix/local.tgz;
}
