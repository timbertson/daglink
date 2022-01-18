{ lib, python3Packages, }:
python3Packages.buildPythonPackage {
  name = "daglink";
  version = lib.fileContents ../VERSION;
  src = ../.;
  propagatedBuildInputs = with python3Packages; [ pyyaml whichcraft ];
  postInstall = ''
    substituteInPlace $out/share/applications/daglink-update.desktop --replace 'daglink -f' "$out/bin/daglink -f"
  '';
}
