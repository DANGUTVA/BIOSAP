SELECT
    F.ProfitCenterName AS [División],
    F.manufacturer      AS [Marca],
    F.itemName          AS [Modelo],
    F.manufSN           AS [Número Serie],
    F.CardCode          AS [Código Cliente],
    F.CardName          AS [Cliente],
    O.U_Localidad       AS [Ubicación],
    O.U_TipoContrato   AS [Tipo Contrato],
    O.U_MontoAnual      AS [Monto Anual],
    O.StartDate          AS [Inicio Contrato],
    O.EndDate            AS [Fin Contrato],
    F.WarrantyStatusName AS [Estado Garantía],
    F.cntrctDate         AS [Vencimiento Garantía],
    F.callType           AS [Tipo Llamada],
    F.createDate         AS [Fecha Llamada]

FROM OCTR O

INNER JOIN CTR1 C
    ON O.ContractID = C.ContractID

INNER JOIN FA_OSCL F
    ON F.insID = C.insID

WHERE
    F.ProfitCenterName = '[%0]'

ORDER BY
    F.CardName,
    F.manufSN