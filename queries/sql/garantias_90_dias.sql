SELECT 
    T0.manufSN AS [Número de Serie],
    T0.internalSN AS [Serial Interno],
    T0.itemCode AS [Código Equipo],
    T0.itemName AS [Equipo],

    T0.CardCode AS [Código Cliente],
    T0.CardName AS [Cliente],

    T0.ProfitCenterName AS [División],

    T0.WarrantyStatusName AS [Estado Garantía],

    T0.cntrctDate AS [Fecha Vencimiento],

    DATEDIFF(DAY, GETDATE(), T0.cntrctDate) AS [Días para vencer],

    COUNT(
        CASE 
            WHEN T0.callType = 2 THEN T0.callID
        END
    ) AS [Cantidad Correctivos]

FROM FA_OSCL T0

WHERE 
    -- División
    T0.ProfitCenterName = 'Imágenes Médicas'

    -- Equipos en garantía
    AND T0.WarrantyStatusName = 'Garantía'

    -- Garantías próximas a vencer
    AND T0.cntrctDate BETWEEN GETDATE()
    AND DATEADD(DAY, 90, GETDATE())

GROUP BY
    T0.manufSN,
    T0.internalSN,
    T0.itemCode,
    T0.itemName,
    T0.CardCode,
    T0.CardName,
    T0.ProfitCenterName,
    T0.WarrantyStatusName,
    T0.cntrctDate

ORDER BY 
    [Días para vencer] ASC,
    [Cantidad Correctivos] DESC
