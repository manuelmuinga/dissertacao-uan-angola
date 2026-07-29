IF FULLTEXTSERVICEPROPERTY('IsFullTextInstalled') = 1
BEGIN
    BEGIN TRY
        EXEC [AmeaçasAngola_DW].dbo.sp_fulltext_database @action = 'enable';
        PRINT N'Full-Text habilitado em [AmeaçasAngola_DW].';
    END TRY
    BEGIN CATCH
        PRINT N'Falha ao habilitar Full-Text em [AmeaçasAngola_DW]: ' + ERROR_MESSAGE();
    END CATCH
END
ELSE
BEGIN
    PRINT N'Full-Text Search não está instalado neste servidor.';
END
GO
