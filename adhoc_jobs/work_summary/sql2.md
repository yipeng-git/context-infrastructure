SELECT
    substr(a.dt1, 1, 7) AS stat_month,
    COALESCE(a.latest_region_name_en, 'UNKNOWN') AS region_name,
    COUNT(DISTINCT CASE WHEN b.is_active = 1 THEN a.wide_user_id END) AS live_tab_mau,
    COUNT(DISTINCT a.wide_user_id) AS active_mau,
    COUNT(DISTINCT CASE WHEN c.host_dau = 1 THEN a.wide_user_id END) AS anchor_mau,
    COUNT(DISTINCT CASE WHEN b.is_buy_crystal = 1 THEN a.wide_user_id END) AS pay_user_cnt,
    COUNT(DISTINCT CASE WHEN b.is_first_buy_crystal = 1 THEN a.wide_user_id END) AS first_pay_user_cnt,
    SUM(COALESCE(b.crystal_rev_cny, 0)) AS crystal_rev_cny,
    SUM(COALESCE(b.crystal_rev_usd, 0)) AS crystal_rev_usd
FROM (
    SELECT
        dt AS dt1,
        latest_region_name_en,
        user_id AS wide_user_id
    FROM dwd.dwd_omi_daily_active_users_info_wide_table_i_d
    WHERE date(dt) >= DATE '2025-04-01'
      AND date(dt) <= CURRENT_DATE
      AND is_active = 1
) a
LEFT JOIN (
    SELECT
        dt AS dt2,
        is_active,
        is_buy_crystal,
        is_first_buy_crystal,
        user_id,
        crystal_rev_cny,
        crystal_rev_usd
    FROM dwd.dwd_omi_live_daily_active_users_info_i_d
    WHERE date(dt) >= DATE '2025-04-01'
      AND date(dt) <= CURRENT_DATE
) b
    ON a.dt1 = b.dt2
   AND a.wide_user_id = b.user_id
LEFT JOIN (
    SELECT
        dt AS dt3,
        user_id AS user_id3,
        is_active AS host_dau
    FROM dwd.dwd_omi_live_anchors_users_info_i_d
    WHERE date(dt) >= DATE '2025-04-01'
      AND date(dt) <= CURRENT_DATE
) c
    ON a.dt1 = c.dt3
   AND a.wide_user_id = c.user_id3
GROUP BY
    1,
    2
ORDER BY
    1,
    2