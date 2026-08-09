from core.kosis_catalog_adapter import KosisCatalogAdapter

def test_catalog_adapter_rejects_wrong_table_response() -> None:
    adapter=KosisCatalogAdapter(lambda _: {"TBL_ID":"OTHER"})
    try: adapter.fetch_table_metadata("DT_TEST")
    except ValueError: return
    assert False
