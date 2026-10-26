param(
    [Parameter(Mandatory=$true)][string]$SourceDirectory,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
$resolvedSource = (Resolve-Path -LiteralPath $SourceDirectory).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $resolvedOutput) { throw 'La ISO de destino ya existe; no se sobrescribe.' }
if (-not (Test-Path -LiteralPath (Join-Path $resolvedSource 'Instalar.exe'))) { throw 'Falta Instalar.exe.' }
$partialOutput = $resolvedOutput + '.' + [Guid]::NewGuid().ToString('N') + '.partial'

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class XboxPortIsoWriter {
    public static long Write(object imageStream, string path) {
        var input = (IStream)imageStream;
        System.Runtime.InteropServices.ComTypes.STATSTG stat;
        input.Stat(out stat, 1);
        byte[] buffer = new byte[1024 * 1024];
        IntPtr readCount = Marshal.AllocHGlobal(4);
        long total = 0;
        try {
            using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write)) {
                while (total < stat.cbSize) {
                    int want = (int)Math.Min(buffer.Length, stat.cbSize - total);
                    input.Read(buffer, want, readCount);
                    int count = Marshal.ReadInt32(readCount);
                    if (count <= 0) throw new EndOfStreamException("Incomplete ISO stream");
                    output.Write(buffer, 0, count);
                    total += count;
                }
                output.Flush(true);
            }
        } finally { Marshal.FreeHGlobal(readCount); }
        return total;
    }
}
'@

$image = New-Object -ComObject IMAPI2FS.MsftFileSystemImage
try {
    # ISO9660 + Joliet + UDF: Windows can mount it as a normal data disc.
    $image.FileSystemsToCreate = 7
    $image.FreeMediaBlocks = 2295104
    $image.VolumeName = 'XBOX_PORT_PC'
    $image.Root.AddTree($resolvedSource, $false)
    $resultImage = $image.CreateResultImage()
    $written = [XboxPortIsoWriter]::Write($resultImage.ImageStream, $partialOutput)
    Move-Item -LiteralPath $partialOutput -Destination $resolvedOutput -ErrorAction Stop
    [pscustomobject]@{ Path=$resolvedOutput; Bytes=$written; Volume='XBOX_PORT_PC' } | ConvertTo-Json
} finally {
    if (Test-Path -LiteralPath $partialOutput) { Remove-Item -LiteralPath $partialOutput -ErrorAction SilentlyContinue }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($image)
}
