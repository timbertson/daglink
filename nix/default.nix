{ lib, pythonPackages, fetchFromGitHub }:
let srcJSON = lib.importJSON ./src.json; in
pythonPackages.buildPythonPackage {
  name = "daglink";
  version = srcJSON.inputs.version;
  src = fetchFromGitHub srcJSON.params;
  propagatedBuildInputs = with pythonPackages; [ pyyaml whichcraft ];
}
