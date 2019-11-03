{ lib, pythonPackages, }:
pythonPackages.buildPythonPackage {
  name = "daglink";
  version = lib.fileContents ../VERSION;
  src = ../.;
  propagatedBuildInputs = with pythonPackages; [ pyyaml whichcraft ];
  postInstall = ''
    substituteInPlace $out/share/applications/daglink-update.desktop --replace 'daglink -f' "$out/bin/daglink -f"
  '';
}
