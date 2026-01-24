package com.example.ems.views;

import com.vaadin.flow.component.applayout.AppLayout;
import com.vaadin.flow.component.applayout.DrawerToggle;
import com.vaadin.flow.component.html.H1;
import com.vaadin.flow.component.orderedlayout.VerticalLayout;
import com.vaadin.flow.router.RouterLink;

public class MainLayout extends AppLayout {
    public MainLayout() {
        H1 title = new H1("Employee System");
        title.getStyle().set("font-size", "var(--lumo-font-size-l)").set("margin", "0");
        addToNavbar(new DrawerToggle(), title);

        VerticalLayout menu = new VerticalLayout();
        menu.add(new RouterLink("Dashboard", DashboardView.class));
        menu.add(new RouterLink("Employees", EmployeeView.class));
        menu.add(new RouterLink("Payroll", PayrollView.class));
        menu.add(new RouterLink("Reports", ReportsView.class));
        addToDrawer(menu);
    }
}
