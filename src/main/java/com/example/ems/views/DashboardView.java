package com.example.ems.views;

import com.example.ems.service.EmployeeService;
import com.vaadin.flow.component.html.*;
import com.vaadin.flow.component.orderedlayout.HorizontalLayout;
import com.vaadin.flow.component.orderedlayout.VerticalLayout;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.router.RouteAlias;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

@Route(value = "dashboard", layout = MainLayout.class)
@RouteAlias(value = "", layout = MainLayout.class) // Default Page
public class DashboardView extends VerticalLayout {
    public DashboardView(EmployeeService service) {
        String currentMonth = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy-MM"));
        double totalPayout = service.fetchPayrollHistory(currentMonth).stream().mapToDouble(d -> d.getDouble("amount")).sum();
        int totalEmp = service.fetchEmployees(true).size();

        add(new H2("Executive Overview"), new HorizontalLayout(
            createCard("Total Active Employees", String.valueOf(totalEmp)),
            createCard("Payroll (" + currentMonth + ")", String.format("$%.2f", totalPayout))
        ));
    }
    private VerticalLayout createCard(String title, String val) {
        VerticalLayout v = new VerticalLayout(new Span(title), new H3(val));
        v.getStyle().set("box-shadow", "0 2px 4px rgba(0,0,0,0.1)").set("padding", "20px").set("border-radius", "10px");
        return v;
    }
}
