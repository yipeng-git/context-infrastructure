WITH active_user_day AS (
    SELECT
        dt,
        substr(dt, 1, 7) AS stat_month,
        user_id,
        COALESCE(arbitrary(latest_region_name_en), 'UNKNOWN') AS region_name
    FROM dwd.dwd_omi_daily_active_users_info_wide_table_i_d
    WHERE dt >= '2025-04-01'
      AND dt <= CAST(CURRENT_DATE AS varchar)
      AND is_active = 1
    GROUP BY
        1,
        2,
        3
),

active_mau AS (
    SELECT
        stat_month,
        region_name,
        COUNT(*) AS active_mau
    FROM (
        SELECT
            stat_month,
            region_name,
            user_id
        FROM active_user_day
        GROUP BY
            1,
            2,
            3
    ) active_user_month
    GROUP BY
        1,
        2
),

live_tab_mau AS (
    SELECT
        stat_month,
        region_name,
        COUNT(*) AS live_tab_mau
    FROM (
        SELECT
            a.stat_month,
            a.region_name,
            a.user_id
        FROM active_user_day a
        INNER JOIN (
            SELECT
                dt,
                user_id
            FROM dwd.dwd_omi_live_daily_active_users_info_i_d
            WHERE dt >= '2025-04-01'
              AND dt <= CAST(CURRENT_DATE AS varchar)
              AND is_active = 1
            GROUP BY
                1,
                2
        ) b
            ON a.dt = b.dt
           AND a.user_id = b.user_id
        GROUP BY
            1,
            2,
            3
    ) live_tab_user_month
    GROUP BY
        1,
        2
),

anchor_mau AS (
    SELECT
        stat_month,
        region_name,
        COUNT(*) AS anchor_mau
    FROM (
        SELECT
            a.stat_month,
            a.region_name,
            a.user_id
        FROM active_user_day a
        INNER JOIN (
            SELECT
                dt,
                user_id
            FROM dwd.dwd_omi_live_anchors_users_info_i_d
            WHERE dt >= '2025-04-01'
              AND dt <= CAST(CURRENT_DATE AS varchar)
              AND is_active = 1
            GROUP BY
                1,
                2
        ) c
            ON a.dt = c.dt
           AND a.user_id = c.user_id
        GROUP BY
            1,
            2,
            3
    ) anchor_user_month
    GROUP BY
        1,
        2
),

pay_metrics AS (
    SELECT
        stat_month,
        region_name,
        SUM(pay_user_flag) AS pay_user_cnt,
        SUM(first_pay_user_flag) AS first_pay_user_cnt,
        SUM(crystal_rev_cny) AS crystal_rev_cny,
        SUM(crystal_rev_usd) AS crystal_rev_usd
    FROM (
        SELECT
            a.stat_month,
            a.region_name,
            a.user_id,
            MAX(b.is_pay_user) AS pay_user_flag,
            MAX(b.is_first_pay_user) AS first_pay_user_flag,
            SUM(b.crystal_rev_cny) AS crystal_rev_cny,
            SUM(b.crystal_rev_usd) AS crystal_rev_usd
        FROM active_user_day a
        INNER JOIN (
            SELECT
                dt,
                user_id,
                MAX(CASE WHEN is_buy_crystal = 1 THEN 1 ELSE 0 END) AS is_pay_user,
                MAX(CASE WHEN is_first_buy_crystal = 1 THEN 1 ELSE 0 END) AS is_first_pay_user,
                SUM(COALESCE(crystal_rev_cny, 0)) AS crystal_rev_cny,
                SUM(COALESCE(crystal_rev_usd, 0)) AS crystal_rev_usd
            FROM dwd.dwd_omi_live_daily_active_users_info_i_d
            WHERE dt >= '2025-04-01'
              AND dt <= CAST(CURRENT_DATE AS varchar)
              AND (
                  is_buy_crystal = 1
                  OR is_first_buy_crystal = 1
                  OR COALESCE(crystal_rev_cny, 0) <> 0
                  OR COALESCE(crystal_rev_usd, 0) <> 0
              )
            GROUP BY
                1,
                2
        ) b
            ON a.dt = b.dt
           AND a.user_id = b.user_id
        GROUP BY
            1,
            2,
            3
    ) pay_user_month
    GROUP BY
        1,
        2
),

metric_union AS (
    SELECT
        stat_month,
        region_name,
        CAST(0 AS bigint) AS live_tab_mau,
        active_mau,
        CAST(0 AS bigint) AS anchor_mau,
        CAST(0 AS bigint) AS pay_user_cnt,
        CAST(0 AS bigint) AS first_pay_user_cnt,
        CAST(0 AS double) AS crystal_rev_cny,
        CAST(0 AS double) AS crystal_rev_usd
    FROM active_mau

    UNION ALL

    SELECT
        stat_month,
        region_name,
        live_tab_mau,
        CAST(0 AS bigint) AS active_mau,
        CAST(0 AS bigint) AS anchor_mau,
        CAST(0 AS bigint) AS pay_user_cnt,
        CAST(0 AS bigint) AS first_pay_user_cnt,
        CAST(0 AS double) AS crystal_rev_cny,
        CAST(0 AS double) AS crystal_rev_usd
    FROM live_tab_mau

    UNION ALL

    SELECT
        stat_month,
        region_name,
        CAST(0 AS bigint) AS live_tab_mau,
        CAST(0 AS bigint) AS active_mau,
        anchor_mau,
        CAST(0 AS bigint) AS pay_user_cnt,
        CAST(0 AS bigint) AS first_pay_user_cnt,
        CAST(0 AS double) AS crystal_rev_cny,
        CAST(0 AS double) AS crystal_rev_usd
    FROM anchor_mau

    UNION ALL

    SELECT
        stat_month,
        region_name,
        CAST(0 AS bigint) AS live_tab_mau,
        CAST(0 AS bigint) AS active_mau,
        CAST(0 AS bigint) AS anchor_mau,
        pay_user_cnt,
        first_pay_user_cnt,
        crystal_rev_cny,
        crystal_rev_usd
    FROM pay_metrics
)

SELECT
    stat_month,
    region_name,
    SUM(live_tab_mau) AS live_tab_mau,
    SUM(active_mau) AS active_mau,
    SUM(anchor_mau) AS anchor_mau,
    SUM(pay_user_cnt) AS pay_user_cnt,
    SUM(first_pay_user_cnt) AS first_pay_user_cnt,
    SUM(crystal_rev_cny) AS crystal_rev_cny,
    SUM(crystal_rev_usd) AS crystal_rev_usd
FROM metric_union
GROUP BY
    1,
    2
ORDER BY
    1,
    2
