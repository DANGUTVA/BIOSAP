SELECT
    T0.CardCode AS [Código Cliente],
    T0.CardName AS [Cliente],
    T0.itemCode AS [Código Equipo],
    T0.itemName AS [Equipo],
    T0.manufSN AS [Número de Serie],
    T0.WarrantyStatus AS [Estado Contrato],
    COUNT(T0.callID) AS [Llamadas Correctivas]

FROM FA_OSCL T0

WHERE
    T0.ProfitCenterName = 'Imágenes Médicas'

GROUP BY
    T0.CardCode,
    T0.CardName,
    T0.itemCode,
    T0.itemName,
    T0.manufSN,
    T0.WarrantyStatus

ORDER BY
    [Llamadas Correctivas] DESC