param(
    [ValidateScript({ $_.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork })]
    [Parameter(Mandatory)][ipaddress]$IP,
    [ValidateRange(1, 1000000)][int]$Muestras = 120
)

$saludo = [byte[]](@(0x21, 0x31, 0, 32) + (@(255) * 28))
$udp = [Net.Sockets.UdpClient]::new()
try {
    $udp.Client.ReceiveTimeout = 1500
    $udp.Connect($IP, 54321)
    $origen = [Net.IPEndPoint]::new([Net.IPAddress]::Any, 0)
    for ($i = 0; $i -lt $Muestras; $i++) {
        $estado = 'sin respuesta miIO'
        try {
            [void]$udp.Send($saludo, $saludo.Length)
            $respuesta = $udp.Receive([ref]$origen)
            if ($respuesta.Length -eq 32 -and $respuesta[0] -eq 0x21 -and $respuesta[1] -eq 0x31 -and $respuesta[2] -eq 0 -and $respuesta[3] -eq 32) {
                $estado = 'miIO responde'
            } else {
                $estado = 'respuesta miIO inesperada'
            }
        } catch [System.Net.Sockets.SocketException] {
            $estado = "sin respuesta miIO ($($_.Exception.SocketErrorCode))"
        }
        '{0:yyyy-MM-dd HH:mm:ss}  {1}  {2}' -f (Get-Date), $IP, $estado
        if ($i + 1 -lt $Muestras) { Start-Sleep -Seconds 5 }
    }
} finally {
    $udp.Dispose()
}
