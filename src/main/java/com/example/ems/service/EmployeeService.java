package com.example.ems.service;

import com.mongodb.client.*;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.bson.Document;
import org.bson.types.ObjectId;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Service
public class EmployeeService {

    private final MongoCollection<Document> empCollection;
    private final MongoCollection<Document> salaryCollection;

    public EmployeeService() {
        // Reads from Environment Variable "MONGO_URI" or defaults to localhost
        String uri = System.getenv("MONGO_URI");
        if (uri == null || uri.isEmpty()) {
            uri = "mongodb://localhost:27017/";
        }
        
        MongoClient client = MongoClients.create(uri);
        MongoDatabase db = client.getDatabase("EmployeeManagementDB");
        this.empCollection = db.getCollection("employees");
        this.salaryCollection = db.getCollection("salaries");
    }

    public List<Document> fetchEmployees(boolean activeOnly) {
        List<Document> list = new ArrayList<>();
        FindIterable<Document> docs = activeOnly ? 
            empCollection.find(Filters.eq("status", "Active")) : 
            empCollection.find();
        docs.into(list);
        return list;
    }

    public String registerEmployee(String empId, String name, String email, String role) {
        if (empCollection.find(Filters.eq("employeeId", empId)).first() != null) {
            return "Error: Employee ID is already in use.";
        }
        Document doc = new Document("employeeId", empId)
                .append("name", name)
                .append("email", email)
                .append("designation", role)
                .append("status", "Active")
                .append("joinedDate", LocalDateTime.now());
        try {
            empCollection.insertOne(doc);
            return "Success: Employee registered.";
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    public void updateEmployee(ObjectId id, String name, String email, String role) {
        empCollection.updateOne(Filters.eq("_id", id), 
            Updates.combine(Updates.set("name", name), Updates.set("email", email), Updates.set("designation", role)));
    }

    public void archiveEmployee(ObjectId id) {
        empCollection.updateOne(Filters.eq("_id", id), Updates.set("status", "Inactive"));
    }

    public String processPayroll(String empId, double amount, String month) {
        Document emp = empCollection.find(Filters.eq("employeeId", empId)).first();
        if (emp == null) return "Error: Employee not found.";
        
        if (salaryCollection.find(Filters.and(Filters.eq("employeeId", empId), Filters.eq("month", month))).first() != null) {
            return "Error: Already processed for this month.";
        }

        Document tx = new Document("employeeId", empId)
                .append("employeeName", emp.getString("name"))
                .append("amount", amount)
                .append("month", month)
                .append("processedDate", LocalDateTime.now());
        salaryCollection.insertOne(tx);
        return "Success: Transaction processed.";
    }

    public List<Document> fetchPayrollHistory(String month) {
        List<Document> list = new ArrayList<>();
        FindIterable<Document> docs = (month != null && !month.isEmpty()) ?
                salaryCollection.find(Filters.eq("month", month)) : salaryCollection.find();
        docs.into(list);
        return list;
    }

    public ByteArrayInputStream generateExcel(List<Document> data) throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Report");
            Row header = sheet.createRow(0);
            String[] cols = {"ID", "Name", "Amount", "Month", "Date"};
            for (int i = 0; i < cols.length; i++) header.createCell(i).setCellValue(cols[i]);

            int rowIdx = 1;
            for (Document doc : data) {
                Row row = sheet.createRow(rowIdx++);
                row.createCell(0).setCellValue(doc.getString("employeeId"));
                row.createCell(1).setCellValue(doc.getString("employeeName"));
                row.createCell(2).setCellValue(doc.getDouble("amount"));
                row.createCell(3).setCellValue(doc.getString("month"));
                row.createCell(4).setCellValue(doc.get("processedDate").toString());
            }
            workbook.write(out);
            return new ByteArrayInputStream(out.toByteArray());
        }
    }
}
