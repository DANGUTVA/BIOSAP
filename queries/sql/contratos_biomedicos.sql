SELECT
    O.ContractID AS [ID Contrato],
    F.CardCode AS [Código Cliente],
    F.CardName AS [Cliente],
    C.ItemCode AS [Código Equipo],
    C.ItemName AS [Equipo],
    C.ManufSN AS [Número Serie],
    O.U_Localidad AS [Ubicación],
    O.U_TipoContrato AS [Tipo Contrato],
    C.U_Monto AS [Monto Equipo],
    O.U_Moneda AS [Moneda],
    C.U_Periodicidad AS [Periodicidad],
    O.StartDate AS [Inicio Contrato],
    O.EndDate AS [Fin Contrato],
    O.Renewal AS [Renovación]

FROM OCTR O

INNER JOIN CTR1 C
    ON O.ContractID = C.ContractID

INNER JOIN FA_OSCL F
    ON F.insID = C.insID

WHERE F.ProfitCenterName = 'Imágenes Médicas'

ORDER BY C.U_Monto DESC