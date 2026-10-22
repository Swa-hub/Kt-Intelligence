from app.gap_detector import _excerpt_is_present, _overlap


def test_exact_excerpt_is_present():
    src = 'def get_order(order_id):\n    row = db.query_one(...)\n    return row'
    assert _excerpt_is_present("def get_order(order_id):", src)


def test_whitespace_insensitive_match():
    src = 'def  get_order (  order_id ):\n   return row'
    assert _excerpt_is_present("def get_order(order_id):\n    return row", src)


def test_hallucinated_excerpt_rejected():
    src = 'def get_order(order_id):\n    return row'
    assert not _excerpt_is_present("def delete_entire_database():\n    rm -rf /", src)


def test_overlap_jaccard():
    assert _overlap("auth decorator missing", "the auth decorator is missing") > 0.5
    assert _overlap("unrelated", "stripe retry policy") < 0.2
