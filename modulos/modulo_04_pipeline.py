"""
Módulo 4 — Pipeline PySpark Structured Streaming
Dissertação UAN — Manuel Muinga 2026 | SO: Windows 11 / Google Colab Pro
"""
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, FloatType, BooleanType
from pyspark.sql.functions import udf

os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/java-11-openjdk-amd64")


def criar_spark_session(jars_dir="/content/jars"):
    """Cria SparkSession com suporte a MongoDB e streaming."""
    jars = ",".join([
        f"{jars_dir}/spark-sql-kafka.jar",
        f"{jars_dir}/commons-pool2.jar",
    ])
    return (
        SparkSession.builder
        .appName("MonitoramentoAmeacasAngola_UAN2026")
        .master("local[*]")
        .config("spark.jars", jars)
        .config("spark.driver.memory", "6g")
        .config("spark.executor.memory", "6g")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


SCHEMA_PUBLICACAO = StructType([
    StructField("id_externo",   StringType(),  True),
    StructField("texto",        StringType(),  True),
    StructField("plataforma",   StringType(),  True),
    StructField("provincia",    StringType(),  True),
    StructField("recolhido_em", StringType(),  True),
])

SCHEMA_RESULTADO = StructType([
    StructField("categoria", StringType(),  True),
    StructField("confianca", FloatType(),   True),
    StructField("alerta",    BooleanType(), True),
])


def criar_udf_bert(modelo_bert, tokenizer, device):
    """Cria UDF Spark para classificação BERT distribuída."""
    import torch, numpy as np
    CATS = {0:"Normal",1:"Desinformação",2:"Discurso de Ódio",3:"Mobilização Hostil"}

    @udf(returnType=SCHEMA_RESULTADO)
    def udf_classificar(texto):
        if not texto or len(texto.strip()) < 3:
            return ("Normal", 1.0, False)
        enc = tokenizer(texto, max_length=128, padding="max_length",
                        truncation=True, return_tensors="pt")
        with torch.no_grad():
            out = modelo_bert(input_ids=enc["input_ids"].to(device),
                              attention_mask=enc["attention_mask"].to(device))
        probs = torch.softmax(out.logits, dim=-1).cpu().numpy()[0]
        cl    = int(np.argmax(probs))
        conf  = float(probs[cl])
        return (CATS[cl], round(conf, 4), conf >= 0.75 and cl != 0)

    return udf_classificar
