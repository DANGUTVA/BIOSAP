SELECT
    T0.ProfitCenterName AS [División],
    T0.itemName AS [Marca],
    T0.itemName AS [Modelo],
    T0.itemCode AS [Código Equipo],
    T0.manufSN AS [Número Serie],
    T0.CardCode AS [Código Cliente],
    T0.CardName AS [Cliente],
    T0.callType AS [Tipo Llamada],
    T0.createDate AS [Fecha Llamada],
    T0.WarrantyStatusName AS [Estado Garantía],
    T0.cntrctDate AS [Vencimiento Garantía]

FROM FA_OSCL T0

WHERE T0.ProfitCenterName = 'Imágenes Médicas'

ORDER BY T0.manufSN, T0.createDate