SELECT
    T0.manufSN AS [Número de Serie],
    T0.internalSN AS [Serial Interno],
    T0.itemCode AS [Código Equipo],
    T0.itemName AS [Equipo],
    T0.CardCode AS [Código Cliente],
    T0.CardName AS [Cliente],
    T0.WarrantyStatus AS [Contrato],

    COUNT(T0.callID) AS [Cantidad Llamadas Correctivas]

FROM FA_OSCL T0

WHERE
    -- Buscar equipo por serial
    T0.manufSN = '[%0]'

    -- Solo equipos sin contrato
    AND T0.WarrantyStatus = 'Sin_Contrato'

    -- Solo llamadas correctivas
    AND T0.callType = 2

GROUP BY
    T0.manufSN,
    T0.internalSN,
    T0.itemCode,
    T0.itemName,
    T0.CardCode,
    T0.CardName,
    T0.WarrantyStatus
