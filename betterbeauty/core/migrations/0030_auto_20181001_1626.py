# Generated by Django 2.1 on 2018-10-01 20:26

from django.db import migrations


def forwards(apps, schema_editor):
    schema_editor.execute(
        '''
        DO
        $do$
        begin
            create or replace view public.rpt_user as
            select u.id,
                u.is_active,
                u.is_staff,
                u.date_joined,
                u.last_login,
            --	u.is_superuser,
            --	u.role,
                ('stylist' = ANY( u.role))::int is_stylist,
                ('client' = ANY( u.role))::int is_client,
                (ii.created_client_id is not null)::int is_invitation
            from public.user u
                left join (
                    select c.user_id, max( i.created_client_id) created_client_id
                    from public.client c
                        left join public.client_of_stylist cs
                            on c.id = cs.client_id
                        left join public.invitation i
                            on cs.id = i.created_client_id
                    group by c.user_id) ii
                on u.id = ii.user_id
            where 'staff' != ALL( u.role)
            ;


            create or replace view public.rpt_staff_users as
            select distinct id
            from public.user
            where 'staff' = ANY(role)
            ;


            create or replace view public.rpt_staff_stylist as
            select distinct s.id
            from public.stylist s
                inner join public.rpt_staff_users u
                on s.user_id = u.id
            ;


            create or replace view public.rpt_staff_client as
            select distinct c.id
            from public.client c
                left join public.rpt_staff_users u
                    on c.user_id = u.id
                left join public.rpt_staff_users s
                    on c.id = s.id
                left join public.preferred_stylist p
                    on s.id = p.stylist_id
            where p.stylist_id is not null or u.id is not null
            ;

            create or replace view public.rpt_appointment_service as
            select
            --	aps.*,
                aps.service_uuid,
                a.datetime_start_at,
            --	a.stylist_id,
                aps.regular_price,
                aps.client_price,
                aps.calculated_price
            from public.appointment_service aps
                inner join public.appointment a
                on aps.appointment_id = a.id
            ;


            create or replace view public.rpt_distribution_clients_per_stylists as
            --Distribution clients per stylist
            select
                a.clients_count,
                substring('   ' || a.clients_count::varchar from '...$') s_clients_count,
                count(distinct a.stylist_id) stylist_count,
                CURRENT_TIMESTAMP datetime
            from (
                select count(distinct client_id) clients_count, stylist_id
                from public.client_of_stylist
                where
                    client_id not in (
                        select id
                        from public.rpt_staff_client)
                    and stylist_id not in (
                        select id
                        from public.rpt_staff_stylist)
                group by stylist_id
                ) a
            group by a.clients_count
            ;


            create or replace view public.rpt_distribution_stylists_per_clients as
            --Distribution stylists per client
            select
                a.stylists_count,
                substring('   ' || a.stylists_count::varchar from '...$') s_stylists_count,
                count(distinct a.client_id) client_count,
                CURRENT_TIMESTAMP datetime
            from (
                select client_id, count(distinct stylist_id) stylists_count
                from public.client_of_stylist
                where
                    client_id not in (
                        select id
                        from public.rpt_staff_client)
                    and stylist_id not in (
                        select id
                        from public.rpt_staff_stylist)
                group by client_id
                ) a
            group by a.stylists_count
            ;


            create or replace view public.rpt_distribution_pareto_stylist_client as
            -- stylists whale curve
            select
                1 g,
                CURRENT_TIMESTAMP datetime,
            --		a.clients_count ,
                (sum(a.clients_count) over (order by a.clients_count desc, a.stylist_id))/
                    (sum( a.clients_count) over (partition by a.g))::float clients_percent,
                (count(a.stylist_id) over (order by a.clients_count desc, a.stylist_id))/
                    (count(a.stylist_id) over (partition by a.g))::float stylist_percent
            from (
                select count(distinct client_id) clients_count, stylist_id, 1 g
                from public.client_of_stylist
                 where
                    client_id not in (
                        select id
                        from public.rpt_staff_client)
                    and stylist_id not in (
                        select id
                        from public.rpt_staff_stylist)
                group by stylist_id
                ) a
            order by 2
            ;


            create or replace view public.rpt_dates as
            select
                date_trunc('day', d):: date dt,
                date_trunc('day', d - interval '1 week' + interval '1 day'):: date dt_week_ago,
                date_trunc('day', d - interval '1 month' + interval '1 day'):: date dt_month_ago
            from generate_series
                    ( '2018-09-01'::timestamp
                    , '2020-12-31'::timestamp
                    , '1 day'::interval) d
            ;



            create or replace view public.rpt_booking as
            select
                --# weekly bookings/stylist
                --# monthly bookings/stylist
                b.id,
                b.datetime_start_at,
                b.stylist_id,
            --	b.client_id,
                --
                --%% completed visits checked out by stylist
                (b.status = 'checked_out')::int is_checked_out,
                --
                --%% cancelled visits / booked
                (b.status in ('cancelled_by_client', 'cancelled_by_stylist'))::int is_cancelled,
                --
                --Avg stylist revenue per week
                --Median stylist revenue per week
                b.grand_total,
                --
                --TODO:Avg booking price
                --TODO:Median booking price
                --
                --%% of discounted bookings
                srv.is_discount,
                --
                --Avg savings per discounted booking
                case when srv.discount_amount > 0 then srv.discount_amount else null end discount_amount,
                --
                --%% of clients rebooking within 3 months
                lag( b.datetime_start_at, 1, null) over previous_booking,
                (b.datetime_start_at - interval '3 months' >
                lag( b.datetime_start_at, 1, null) over previous_booking)::int rebooking_3_months,
                --
                --%% of clients rebooking within 6 months
                (b.datetime_start_at - interval '6 months' >
                lag( b.datetime_start_at, 1, null) over previous_booking)::int rebooking_6_months,
                --
                --%% of bookings with 2 or more services
                --%% of completed visits with 2 or more services
                srv.services_count,
                (srv.services_count>=2)::int is_two_and_more_services
            from public.appointment b
                left join (
                    select s.appointment_id,
                        sum(s.regular_price - s.client_price) discount_amount,
                        max((s.applied_discount is not null)::int) is_discount,
                        count(s.id) services_count
                    from public.appointment_service s
                    group by s.appointment_id
                ) srv
                    on b.id = srv.appointment_id
                left join public.rpt_staff_client sc
                    on b.client_id = sc.id
                left join public.rpt_staff_stylist ss
                    on b.stylist_id = ss.id
            where
                sc.id is null
                and ss.id is null
            window previous_booking as (partition by b.client_id order by b.datetime_start_at)
            ;


            create or replace view public.rpt_stylist as
            select
                st.id stylist_id,
                --
                -- Avg # of services per stylist
                coalesce( srv.stylist_services_count, 0) stylist_services_count,
                --
                --Avg price per stylist services (base price)
                --Median price of stylist services (base price)
                srv.avg_regular_price,
                --
                --%% of stylist with daily discount
                coalesce( wd.weekday_discounts_count, 0)::int weekday_discounts_count,
                case when coalesce( wd.weekday_discounts_count, 0) > 0 then 1 else 0 end is_daily_discount,
                --
                --Avg %% of daily discount
                coalesce( wd.avg_weekday_discount, 0) avg_weekday_discount,
                --
                --%% of stylist with loyalty discount
                (st.rebook_within_1_week_discount_percent +
                    st.rebook_within_2_weeks_discount_percent +
                    st.rebook_within_3_weeks_discount_percent +
                    st.rebook_within_4_weeks_discount_percent +
                    st.rebook_within_5_weeks_discount_percent +
                    st.rebook_within_6_weeks_discount_percent > 0)::int is_loyalty_discount,
                --
                --Avg %% loyalty discount
                case when 0 = all(array[
                    st.rebook_within_1_week_discount_percent,
                    st.rebook_within_2_weeks_discount_percent,
                    st.rebook_within_3_weeks_discount_percent,
                    st.rebook_within_4_weeks_discount_percent,
                    st.rebook_within_5_weeks_discount_percent,
                    st.rebook_within_6_weeks_discount_percent])
                    then 0
                    else
                    (st.rebook_within_1_week_discount_percent +
                    st.rebook_within_2_weeks_discount_percent +
                    st.rebook_within_3_weeks_discount_percent +
                    st.rebook_within_4_weeks_discount_percent +
                    st.rebook_within_5_weeks_discount_percent +
                    st.rebook_within_6_weeks_discount_percent) /
                    ((st.rebook_within_1_week_discount_percent > 0)::int +
                    (st.rebook_within_2_weeks_discount_percent > 0)::int +
                    (st.rebook_within_3_weeks_discount_percent > 0)::int +
                    (st.rebook_within_4_weeks_discount_percent > 0)::int +
                    (st.rebook_within_5_weeks_discount_percent > 0)::int +
                    (st.rebook_within_6_weeks_discount_percent > 0)::int) end avg_loyalty_discount,
                --
                --%% of stylist with first visit discount
                (st.rebook_within_1_week_discount_percent > 0)::int is_first_week_discount,
                --
                --Avg %% first visit discount
                st.first_time_book_discount_percent,
                st.rebook_within_1_week_discount_percent,
                --
                --%% of stylist with max discount
                (st.maximum_discount > 0 and st.is_maximum_discount_enabled)::int is_maximum_discount_enabled,
                --
                --Avg amt max discount
                case when not st.is_maximum_discount_enabled then null else st.maximum_discount end maximum_discount,
                --
                --%% of stylist with no discounts
                (0 = all(array[
                    st.rebook_within_1_week_discount_percent,
                    st.rebook_within_2_weeks_discount_percent,
                    st.rebook_within_3_weeks_discount_percent,
                    st.rebook_within_4_weeks_discount_percent,
                    st.rebook_within_5_weeks_discount_percent,
                    st.rebook_within_6_weeks_discount_percent,
                    st.is_maximum_discount_enabled::int,
                    coalesce( wd.weekday_discounts_count, 0)]))::int no_discount_count
            from public.stylist st
                left join (
                    select ss.stylist_id,
                        count( ss.id) stylist_services_count,
                        avg( ss.regular_price) avg_regular_price
                    from public.stylist_service ss
                    where ss.is_enabled = true and ss.deleted_at is null
                    group by ss.stylist_id
                ) srv
                on st.id = srv.stylist_id
                left join (
                    select swd.stylist_id,
                        count( swd.id) weekday_discounts_count,
                        avg( swd.discount_percent) avg_weekday_discount
                    from public.stylist_weekday_discount swd
                    where swd.discount_percent > 0
                    group by swd.stylist_id
                ) wd
                on st.id = wd.stylist_id
                inner join public."user" u
                on st.user_id = u.id
            where st.id not in (
                select id
                from public.rpt_staff_stylist)
            ;


        end
        $do$;
        '''
    )


def backwards(apps, schema_editor):
    schema_editor.execute(
        '''
        DO
        $do$
        begin
            drop view if exists public.rpt_appointment_service;
            drop view if exists public.rpt_distribution_clients_per_stylists;
            drop view if exists public.rpt_distribution_stylists_per_clients;
            drop view if exists public.rpt_distribution_pareto_stylist_client;
            drop view if exists public.rpt_stylist;
            drop view if exists public.rpt_dates;
            drop view if exists public.rpt_user;
            drop view if exists public.rpt_booking;
            drop view if exists public.rpt_staff_client;
            drop view if exists public.rpt_staff_stylist;
            drop view if exists public.rpt_staff_users;
        end
        $do$;
        '''
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_auto_20180927_1112'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards)
    ]
