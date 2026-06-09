SELECT dt1,
       is_active,
       gender,
       status,
       day_in_app,
       latest_region_name_en,
       latest_os_name,
       is_premium_user,
       is_supreme_user,
       is_buy_crystal,
       is_first_buy_crystal,
       ROLE,
       wide_user_id,
       user_id,
       returned_1d,
       is_consume_consultation,
       crystal_rev_cny,
       crystal_rev_usd,
       host_dau,
       tixian_coins,
       lishi_weixiaohao_coins,
       lishi_weixiaohao_diamonds
FROM
  (SELECT dt AS dt1,
          gender,
          status,
          day_in_app,
          latest_region_name_en,
          latest_os_name,
          is_premium_user,
          is_supreme_user,
          user_id AS wide_user_id
   FROM dwd.dwd_omi_daily_active_users_info_wide_table_i_d
   WHERE date(dt) >= date(CURRENT_DATE - interval '400' DAY)
     AND is_active = 1) a
LEFT JOIN
  (SELECT dt AS dt2,
          is_active,
          is_buy_crystal,
          is_first_buy_crystal,
          ROLE,
          user_id,
          returned_1d,
          crystal_rev_cny,
          crystal_rev_usd,
          is_consume_consultation
   FROM dwd.dwd_omi_live_daily_active_users_info_i_d
   WHERE date(dt) >= date(CURRENT_DATE - interval '240' DAY) ) b ON a.dt1 = b.dt2
AND a.wide_user_id = b.user_id
LEFT JOIN
  (SELECT dt AS dt3,
  user_id as user_id3,
          is_active AS host_dau
   FROM dwd.dwd_omi_live_anchors_users_info_i_d) c ON a.dt1 = c.dt3 and a.wide_user_id = c.user_id3
   
   
left JOIN 
(SELECT substr(created_time,1,10) AS dt4,
user_id as user_id4,
sum(coins) as tixian_coins
 FROM dwd.dwd_db_omi_putong_wallet_yay_withdrawals_a_d
 WHERE withdrawal_status = 'success'
 GROUP BY 1,2) d 
   
   ON a.dt1 = d.dt4 and c.user_id3 = d.user_id4
   
   
left JOIN 
(SELECT dt AS dt5,
user_id as user_id5,
       SUM(coins_balance) AS lishi_weixiaohao_coins,
       SUM(diamonds_balance) AS lishi_weixiaohao_diamonds
FROM dwd.dwd_db_omi_putong_wallet_yay_wallets_a_d
WHERE dt IN (
    CAST(date_trunc('month', current_date) - interval '1' day AS varchar), -- 上个月的最后一天
    CAST(date_trunc('month', current_date) - interval '1' month - interval '1' day AS varchar), -- 上上个月的最后一天
    CAST(date_trunc('month', current_date) - interval '2' month - interval '1' day AS varchar), -- 上上上个月的最后一天
    CAST(current_date - interval '1' day AS varchar) -- 昨天
)
GROUP BY 1,2) e 
 ON a.dt1 = e.dt5 and a.wide_user_id = e.user_id5

   
GROUP BY 1,
         2,
         3,
         4,
         5,
         6,
         7,
         8,
         9,
         10,
         11,
         12,
         13,
         14,
         15,
         16,
         17,
         18,
         19,20,21,22