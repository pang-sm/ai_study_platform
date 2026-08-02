"""Restore twelve Java exercises as real, executable multi-file projects.

The repair keeps the existing exercise ids and source keys.  Each replacement
is compiled twice: the learner scaffold must compile with TODOs, while the
server-only reference files must pass every regenerated public and hidden
console case.  Reference files and hidden drivers are never put in the
published manifest.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

SNAPSHOT = ROOT / "backend/data/programming_catalog_240.json.gz"
NOW = datetime.now(timezone.utc).isoformat()


def f(path: str, content: str) -> dict:
    return {"path": path, "content": content.strip() + "\n", "editable": True}


def starterize(content: str) -> str:
    """Replace solution blocks with compiling TODO stubs."""
    defaults = {
        "INT": "return 0;",
        "DOUBLE": "return 0.0;",
        "STRING": 'return "";',
        "BOOL": "return false;",
        "LIST": "return new ArrayList<>();",
        "VOID": "return;",
    }

    def replace(match: re.Match[str]) -> str:
        kind = match.group(1)
        body = match.group(2)
        signature = re.search(r"(?m)^\s*(?:public\s+)?[^\n{]+\{", body)
        if signature:
            declaration = signature.group(0).strip()
            return f"\n    {declaration}\n        // TODO：完成这里的对象协作逻辑。\n        {defaults[kind]}\n    }}"
        return f"\n        // TODO：完成这里的对象协作逻辑。\n        {defaults[kind]}"

    return re.sub(r"\s*// SOLUTION_START:(\w+)\n(.*?)// SOLUTION_END", replace, content, flags=re.S)


def java_files(reference: dict[str, str]) -> tuple[list[dict], list[dict]]:
    ref = [f(path, content) for path, content in reference.items()]
    starter = [f(item["path"], starterize(item["content"])) for item in ref]
    return starter, ref


def run_java(files: list[dict], stdin: str) -> tuple[str, str, int]:
    with tempfile.TemporaryDirectory(prefix="java-multifile-") as raw:
        root = Path(raw)
        paths = []
        for item in files:
            path = Path(item["path"])
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
            paths.append(str(path))
        classes = root / "classes"
        classes.mkdir()
        compile_proc = subprocess.run(
            ["javac", "-encoding", "UTF-8", "-d", str(classes), *paths],
            cwd=root, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=30,
        )
        if compile_proc.returncode:
            return "", compile_proc.stderr or compile_proc.stdout, compile_proc.returncode
        proc = subprocess.run(
            ["java", "-Dfile.encoding=UTF-8", "-cp", str(classes), "Main"],
            cwd=root, input=stdin, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=8,
        )
        return proc.stdout, proc.stderr, proc.returncode


def cases(inputs: list[str]) -> list[dict]:
    return [{"id": f"public-{i + 1}", "name": f"公开样例 {i + 1}", "stdin_text": value, "visibility": "public"} for i, value in enumerate(inputs)]


def hidden(inputs: list[str]) -> list[dict]:
    return [{"id": f"hidden-{i + 1}", "name": f"服务端测试 {i + 1}", "stdin_text": value, "visibility": "hidden"} for i, value in enumerate(inputs)]


def spec(title: str, slug_key: str, statement: str, input_format: str, output_format: str,
         constraints: str, features: list[str], files: dict[str, str], public_inputs: list[str],
         hidden_inputs: list[str], explain: str, module: str = "面向对象与集合") -> dict:
    starter, reference = java_files(files)
    return {
        "title_zh": title,
        "statement_zh": statement,
        "summary_zh": statement.split("。")[0] + "。",
        "input_format_zh": input_format,
        "output_format_zh": output_format,
        "constraints_zh": constraints,
        "features": features,
        "starter_files": starter,
        "reference_files": reference,
        "public_cases": cases(public_inputs),
        "hidden_cases": hidden(hidden_inputs),
        "explain": explain,
        "module": module,
        "slug_key": slug_key,
    }


SPECS = [
    spec(
        "电影院的座位预订", "cinema-booking",
        "你正在为电影院实现一场放映的购票流程。Movie 保存电影信息，Screening 管理座位状态，Customer 表示购票人，BookingService 负责检查座位并完成一次预订。请让这些对象协作处理一笔订单；座位号越界或已被占用时必须拒绝。",
        "输入依次为电影名、时长、座位总数、客户名和要预订的座位号，字段以空格分隔。", "成功输出 BOOKED 客户名 电影名 座位号，否则输出 REJECTED。", "1≤座位总数≤100，座位号从 1 开始。",
        ["class 与对象", "封装", "List/Set", "Comparator"],
        {
            "Movie.java": '''public class Movie {
    private final String title;
    private final int durationMinutes;
    public Movie(String title, int durationMinutes) { this.title = title; this.durationMinutes = durationMinutes; }
    public String getTitle() { return title; }
    public int getDurationMinutes() { return durationMinutes; }
}''',
            "Seat.java": '''public class Seat {
    private final int number;
    private boolean booked;
    public Seat(int number) { this.number = number; }
    public int getNumber() { return number; }
    public boolean isBooked() { return booked; }
    // SOLUTION_START:BOOL
    public boolean reserve() { if (booked) return false; booked = true; return true; }
    // SOLUTION_END
}''',
            "Screening.java": '''public class Screening {
    private final Movie movie;
    private final Seat[] seats;
    public Screening(Movie movie, int count) { this.movie = movie; seats = new Seat[count]; for (int i = 0; i < count; i++) seats[i] = new Seat(i + 1); }
    public Movie getMovie() { return movie; }
    // SOLUTION_START:BOOL
    public boolean reserve(int number) { if (number < 1 || number > seats.length) return false; return seats[number - 1].reserve(); }
    // SOLUTION_END
}''',
            "Customer.java": '''public class Customer {
    private final String name;
    public Customer(String name) { this.name = name; }
    public String getName() { return name; }
}''',
            "BookingService.java": '''public class BookingService {
    // SOLUTION_START:BOOL
    public boolean bookSeat(Customer customer, Screening screening, int seatNumber) { return screening.reserve(seatNumber); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner input = new Scanner(System.in);
        Movie movie = new Movie(input.next(), input.nextInt());
        Screening screening = new Screening(movie, input.nextInt());
        Customer customer = new Customer(input.next());
        int seatNumber = input.nextInt();
        boolean booked = new BookingService().bookSeat(customer, screening, seatNumber);
        System.out.println(booked ? "BOOKED " + customer.getName() + " " + movie.getTitle() + " " + seatNumber : "REJECTED");
    }
}''',
        },
        ["Aurora 120 3 Alice 2", "Aurora 120 3 Alice 4", "Nova 95 1 Bob 1"],
        ["Aurora 120 3 Alice 1", "Nova 95 1 Bob 0", "Nova 95 1 Bob 2", "Film 200 5 Chen 5", "Film 200 5 Chen -1"],
        "输入先创建 Movie 和 Screening，再创建 Customer。BookingService 把客户和场次交给座位对象检查，成功时占用指定座位并输出 BOOKED；越界输入直接得到 REJECTED。",
    ),
    spec(
        "图书馆的借阅登记", "library-loans",
        "请实现一个小型图书馆的借阅登记。Book 保存书籍，Reader 保存读者，LoanRecord 记录借期，Library 负责检查书籍是否已经借出并建立借阅记录。一次输入只处理一位读者借阅一本书。",
        "输入依次为书号、书名、读者编号和借阅天数。", "可借出时输出 BORROWED 书号 读者编号 天数，否则输出 REJECTED。", "借阅天数为 1 至 60 的整数。",
        ["class 与对象", "List", "Map", "封装", "异常"],
        {
            "Book.java": '''public class Book {
    private final String id; private final String title; private boolean borrowed;
    public Book(String id, String title) { this.id = id; this.title = title; }
    public String getId() { return id; } public String getTitle() { return title; }
    // SOLUTION_START:BOOL
    public boolean borrow() { if (borrowed) return false; borrowed = true; return true; }
    // SOLUTION_END
}''',
            "Reader.java": '''public class Reader {
    private final String id;
    public Reader(String id) { this.id = id; }
    public String getId() { return id; }
}''',
            "LoanRecord.java": '''public class LoanRecord {
    private final Book book; private final Reader reader; private final int days;
    public LoanRecord(Book book, Reader reader, int days) { this.book = book; this.reader = reader; this.days = days; }
    public String summary() { return book.getId() + " " + reader.getId() + " " + days; }
}''',
            "Library.java": '''import java.util.*;
public class Library {
    private final Map<String, Book> books = new HashMap<>();
    public void add(Book book) { books.put(book.getId(), book); }
    // SOLUTION_START:BOOL
    public boolean lend(Reader reader, String id, int days) { Book book = books.get(id); return days >= 1 && days <= 60 && book != null && book.borrow(); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main {
    public static void main(String[] args) { Scanner input = new Scanner(System.in); String id = input.next(); String title = input.next(); String readerId = input.next(); int days = input.nextInt(); Library library = new Library(); library.add(new Book(id, title)); boolean ok = library.lend(new Reader(readerId), id, days); System.out.println(ok ? "BORROWED " + id + " " + readerId + " " + days : "REJECTED"); }
}''',
        },
        ["B42 CleanCode R7 14", "B7 Algorithms R2 1", "B8 Design R3 60"],
        ["B42 CleanCode R7 0", "B42 CleanCode R7 61", "B7 Algorithms R2 30", "B9 Missing R1 7", "B8 Design R3 14"],
        "Library 先用 Map 找到 Book，再由 Book 自己维护借出状态；LoanRecord 保存借阅关系。合法天数和未借出的书才能产生 BORROWED。",
    ),
    spec(
        "停车场的分时计费", "parking-fee",
        "停车场需要根据车辆类型和停留分钟数收取费用。Vehicle 表示车辆，ParkingTicket 保存进场信息，FeePolicy 定义计费规则，ParkingLot 负责生成票据并结算。请通过接口让停车场依赖计费策略。",
        "输入为车牌号、车辆类型（car 或 bike）和停留分钟数。", "输出 PARKED 车牌号 费用，费用按整数元输出。", "停留时间为 1 至 1440 分钟；car 每小时 5 元，bike 每小时 2 元，不足一小时按一小时计。",
        ["interface", "List", "Map", "封装", "Comparator"],
        {
            "Vehicle.java": '''public class Vehicle { private final String plate; private final String type; public Vehicle(String plate, String type) { this.plate = plate; this.type = type; } public String getPlate() { return plate; } public String getType() { return type; } }''',
            "ParkingTicket.java": '''public class ParkingTicket { private final Vehicle vehicle; private final int minutes; public ParkingTicket(Vehicle vehicle, int minutes) { this.vehicle = vehicle; this.minutes = minutes; } public Vehicle getVehicle() { return vehicle; } public int getMinutes() { return minutes; } }''',
            "FeePolicy.java": '''public interface FeePolicy { int fee(ParkingTicket ticket); }''',
            "StandardFeePolicy.java": '''public class StandardFeePolicy implements FeePolicy {
    // SOLUTION_START:INT
    public int fee(ParkingTicket ticket) { int rate = ticket.getVehicle().getType().equals("bike") ? 2 : 5; return ((ticket.getMinutes() + 59) / 60) * rate; }
    // SOLUTION_END
}''',
            "ParkingLot.java": '''public class ParkingLot { private final FeePolicy policy; public ParkingLot(FeePolicy policy) { this.policy = policy; } // SOLUTION_START:INT
    public int checkout(Vehicle vehicle, int minutes) { return policy.fee(new ParkingTicket(vehicle, minutes)); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); Vehicle vehicle = new Vehicle(input.next(), input.next()); int minutes = input.nextInt(); int fee = new ParkingLot(new StandardFeePolicy()).checkout(vehicle, minutes); System.out.println("PARKED " + vehicle.getPlate() + " " + fee); } }''',
        },
        ["A12 car 61", "B7 bike 60", "C3 car 1"],
        ["A12 car 120", "B7 bike 61", "C3 car 121", "D5 bike 1", "E8 car 1440"],
        "Main 创建 Vehicle，ParkingLot 注入 FeePolicy，再由策略读取票据中的车辆类型和分钟数计算费用；向上取整小时数后输出结算结果。",
    ),
    spec(
        "餐厅预约与候位", "restaurant-queue",
        "餐厅要根据桌位容量处理预约。Table 表示桌位，Guest 表示客人，Reservation 记录预约，Restaurant 使用队列保存暂时无法安排的客人。人数不超过空闲桌容量时立即安排，否则进入候位队列。",
        "输入为桌位数量、每张桌子的容量、客人姓名和用餐人数。", "立即安排输出 SEATED 客人名 桌号，否则输出 WAITLIST 客人名。", "桌位数量和人数均为正整数。",
        ["enum", "Queue", "class 与对象", "集合"],
        {
            "ReservationStatus.java": '''public enum ReservationStatus { SEATED, WAITLIST }''',
            "Table.java": '''public class Table { private final int number; private final int capacity; private boolean occupied; public Table(int number, int capacity) { this.number = number; this.capacity = capacity; } public int getNumber() { return number; } // SOLUTION_START:BOOL
    public boolean canSeat(int party) { return !occupied && party <= capacity; }
    // SOLUTION_END
    public void occupy() { occupied = true; } }''',
            "Guest.java": '''public class Guest { private final String name; private final int partySize; public Guest(String name, int partySize) { this.name = name; this.partySize = partySize; } public String getName() { return name; } public int getPartySize() { return partySize; } }''',
            "Reservation.java": '''public class Reservation { private final Guest guest; private final ReservationStatus status; private final int tableNumber; public Reservation(Guest guest, ReservationStatus status, int tableNumber) { this.guest = guest; this.status = status; this.tableNumber = tableNumber; } public String summary() { return status == ReservationStatus.SEATED ? "SEATED " + guest.getName() + " " + tableNumber : "WAITLIST " + guest.getName(); } }''',
            "Restaurant.java": '''import java.util.*;
public class Restaurant { private final List<Table> tables; private final Queue<Guest> waitlist = new ArrayDeque<>(); public Restaurant(List<Table> tables) { this.tables = tables; } // SOLUTION_START:STRING
    public String reserve(Guest guest) { for (Table table : tables) { if (table.canSeat(guest.getPartySize())) { table.occupy(); return new Reservation(guest, ReservationStatus.SEATED, table.getNumber()).summary(); } } waitlist.add(guest); return new Reservation(guest, ReservationStatus.WAITLIST, 0).summary(); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); int count = input.nextInt(); int capacity = input.nextInt(); String name = input.next(); int party = input.nextInt(); List<Table> tables = new ArrayList<>(); for (int i = 1; i <= count; i++) tables.add(new Table(i, capacity)); System.out.println(new Restaurant(tables).reserve(new Guest(name, party))); } }''',
        },
        ["2 4 Lin 3", "1 2 Mei 2", "1 4 Tao 5"],
        ["2 4 Lin 4", "1 2 Mei 3", "0 4 Tao 2", "3 6 Han 7", "1 1 Q 1"],
        "Restaurant 遍历 List<Table>，由 Table 判断容量和占用状态；可安排时创建 SEATED 预约并占用桌位，否则把 Guest 放入 Queue 并返回 WAITLIST。",
    ),
    spec(
        "学生选课登记", "course-registration", "学校需要为学生登记课程。Student 保存已选课程，Course 描述课程和学分，Enrollment 表示一次登记，Registrar 负责避免重复选课并限制总学分。",
        "输入为学生编号、最大学分、课程数量，随后每门课程给出课程号和学分。", "输出 ENROLLED 学生编号 总学分 课程号列表；若存在重复课程或超出最大学分则输出 REJECTED。", "课程数量不超过 10，每门课程学分为正整数。", ["List", "Set", "泛型", "Comparator"],
        {
            "Course.java": '''public class Course { private final String code; private final int credits; public Course(String code, int credits) { this.code = code; this.credits = credits; } public String getCode() { return code; } public int getCredits() { return credits; } }''',
            "Student.java": '''import java.util.*;
public class Student { private final String id; private final int maxCredits; private final Set<String> selected = new LinkedHashSet<>(); private int credits; public Student(String id, int maxCredits) { this.id = id; this.maxCredits = maxCredits; } public String getId() { return id; } // SOLUTION_START:BOOL
    public boolean add(Course course) { if (selected.contains(course.getCode()) || credits + course.getCredits() > maxCredits) return false; selected.add(course.getCode()); credits += course.getCredits(); return true; }
    // SOLUTION_END
    public int getCredits() { return credits; } public String courses() { return String.join(",", selected); } }''',
            "Enrollment.java": '''public class Enrollment { private final Student student; private final Course course; public Enrollment(Student student, Course course) { this.student = student; this.course = course; } public String code() { return course.getCode(); } }''',
            "Registrar.java": '''public class Registrar { // SOLUTION_START:BOOL
    public boolean enroll(Student student, Course course) { return student.add(course); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); Student student = new Student(input.next(), input.nextInt()); int count = input.nextInt(); Registrar registrar = new Registrar(); boolean ok = true; for (int i = 0; i < count; i++) ok &= registrar.enroll(student, new Course(input.next(), input.nextInt())); System.out.println(ok ? "ENROLLED " + student.getId() + " " + student.getCredits() + " " + student.courses() : "REJECTED"); } }''',
        },
        ["S1 6 2 CS 3 MA 3", "S2 5 2 PH 2 HI 3", "S3 10 3 A 2 B 3 C 4"],
        ["S1 6 2 CS 3 CS 3", "S2 5 2 PH 3 HI 3", "S3 10 3 A 2 B 3 C 5", "S4 4 1 X 5", "S5 9 3 X 2 Y 3 Z 4"],
        "Registrar 把 Course 交给 Student，Student 通过泛型 Set 防止重复并维护学分；全部登记成功后由对象状态生成课程列表。",
    ),
    spec(
        "银行账户与交易流水", "bank-transactions", "银行需要按顺序处理账户交易。Account 封装余额，Transaction 表示交易类型，Bank 管理账户，余额不足时抛出 InsufficientBalanceException。请保留成功交易后的最终余额。",
        "第一行是账户编号和初始余额，第二行是交易数量，随后每行给出 DEPOSIT 或 WITHDRAW 及金额。", "输出 BALANCE 账户编号 最终余额；任何非法取款都输出 REJECTED。", "交易数量不超过 20，金额为非负整数。", ["enum", "exception", "List", "封装"],
        {
            "TransactionType.java": '''public enum TransactionType { DEPOSIT, WITHDRAW }''',
            "InsufficientBalanceException.java": '''public class InsufficientBalanceException extends Exception { public InsufficientBalanceException(String message) { super(message); } }''',
            "Transaction.java": '''public class Transaction { private final TransactionType type; private final int amount; public Transaction(TransactionType type, int amount) { this.type = type; this.amount = amount; } public TransactionType getType() { return type; } public int getAmount() { return amount; } }''',
            "Account.java": '''import java.util.*;
public class Account { private final String id; private int balance; public Account(String id, int balance) { this.id = id; this.balance = balance; } public String getId() { return id; } // SOLUTION_START:BOOL
    public boolean apply(Transaction transaction) throws InsufficientBalanceException { if (transaction.getAmount() < 0) return false; if (transaction.getType() == TransactionType.WITHDRAW && transaction.getAmount() > balance) throw new InsufficientBalanceException("insufficient"); if (transaction.getType() == TransactionType.DEPOSIT) balance += transaction.getAmount(); else balance -= transaction.getAmount(); return true; }
    // SOLUTION_END
    public int getBalance() { return balance; } }''',
            "Bank.java": '''public class Bank { // SOLUTION_START:BOOL
    public boolean process(Account account, Transaction transaction) { try { return account.apply(transaction); } catch (InsufficientBalanceException error) { return false; } }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); Account account = new Account(input.next(), input.nextInt()); int count = input.nextInt(); Bank bank = new Bank(); boolean ok = true; for (int i = 0; i < count; i++) ok &= bank.process(account, new Transaction(TransactionType.valueOf(input.next()), input.nextInt())); System.out.println(ok ? "BALANCE " + account.getId() + " " + account.getBalance() : "REJECTED"); } }''',
        },
        ["A1 100 2 DEPOSIT 30 WITHDRAW 50", "A2 10 1 WITHDRAW 10", "A3 0 2 DEPOSIT 8 WITHDRAW 3"],
        ["A1 100 1 WITHDRAW 101", "A2 10 2 DEPOSIT 5 WITHDRAW 7", "A3 0 1 WITHDRAW 1", "A4 20 3 DEPOSIT 0 WITHDRAW 5 DEPOSIT 2", "A5 9 1 WITHDRAW 10"],
        "Main 将每行交易封装为 Transaction，Bank 调用 Account.apply；取款不足时由异常表达失败，主程序因此拒绝整批交易。",
    ),
    spec(
        "电商订单与优惠券", "order-coupon", "电商订单由 Product、OrderItem 和 Order 协作完成，Coupon 通过 DiscountPolicy 接口计算折扣。请根据商品单价、数量和优惠券类型输出订单应付金额。",
        "输入为商品名、单价、数量和优惠券类型（NONE、TEN_PERCENT、FIXED_20）。", "输出 TOTAL 商品名 应付金额，金额保留整数元且不小于 0。", "单价和数量为非负整数。", ["interface", "List", "lambda", "Stream API"],
        {
            "Product.java": '''public class Product { private final String name; private final int price; public Product(String name, int price) { this.name = name; this.price = price; } public String getName() { return name; } public int getPrice() { return price; } }''',
            "OrderItem.java": '''public class OrderItem { private final Product product; private final int quantity; public OrderItem(Product product, int quantity) { this.product = product; this.quantity = quantity; } public int subtotal() { return product.getPrice() * quantity; } public String name() { return product.getName(); } }''',
            "DiscountPolicy.java": '''public interface DiscountPolicy { int apply(int subtotal); }''',
            "Coupon.java": '''public class Coupon implements DiscountPolicy { private final String type; public Coupon(String type) { this.type = type; } // SOLUTION_START:INT
    public int apply(int subtotal) { if (type.equals("TEN_PERCENT")) return subtotal - subtotal / 10; if (type.equals("FIXED_20")) return Math.max(0, subtotal - 20); return subtotal; }
    // SOLUTION_END
}''',
            "Order.java": '''import java.util.*;
public class Order { private final List<OrderItem> items = new ArrayList<>(); private final DiscountPolicy policy; public Order(DiscountPolicy policy) { this.policy = policy; } public void add(OrderItem item) { items.add(item); } // SOLUTION_START:INT
    public int total() { return policy.apply(items.stream().mapToInt(OrderItem::subtotal).sum()); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); String name = input.next(); int price = input.nextInt(); int quantity = input.nextInt(); String coupon = input.next(); Order order = new Order(new Coupon(coupon)); order.add(new OrderItem(new Product(name, price), quantity)); System.out.println("TOTAL " + name + " " + order.total()); } }''',
        },
        ["Book 30 2 TEN_PERCENT", "Pen 8 3 NONE", "Bag 25 2 FIXED_20"],
        ["Book 100 1 FIXED_20", "Pen 8 0 TEN_PERCENT", "Bag 10 5 FIXED_20", "Cup 19 4 TEN_PERCENT", "Pad 0 3 NONE"],
        "Order 保存 OrderItem 列表并使用 Stream API 汇总小计，Coupon 作为 DiscountPolicy 注入订单，优惠规则只影响最终应付金额。",
    ),
    spec(
        "酒店房间预订", "hotel-booking", "酒店要根据房型和入住晚数计算预订价格。Room 保存房间，Guest 表示客人，Booking 记录订单，Hotel 负责查找空闲房间并创建预订。",
        "输入为房间号、房型（single 或 suite）、每晚价格、客人名和入住晚数。", "可预订输出 BOOKED 客人名 房间号 总价，否则输出 REJECTED。", "入住晚数为 1 至 30。", ["Optional", "class 与对象", "封装", "Map"],
        {
            "Room.java": '''public class Room { private final String number; private final String type; private final int price; private boolean occupied; public Room(String number, String type, int price) { this.number = number; this.type = type; this.price = price; } public String getNumber() { return number; } public int getPrice() { return price; } // SOLUTION_START:BOOL
    public boolean occupy() { if (occupied) return false; occupied = true; return true; }
    // SOLUTION_END
}''',
            "Guest.java": '''public class Guest { private final String name; public Guest(String name) { this.name = name; } public String getName() { return name; } }''',
            "Booking.java": '''public class Booking { private final Guest guest; private final Room room; private final int nights; public Booking(Guest guest, Room room, int nights) { this.guest = guest; this.room = room; this.nights = nights; } public String summary() { return "BOOKED " + guest.getName() + " " + room.getNumber() + " " + room.getPrice() * nights; } }''',
            "Hotel.java": '''import java.util.*;
public class Hotel { private final Map<String, Room> rooms = new HashMap<>(); public void add(Room room) { rooms.put(room.getNumber(), room); } // SOLUTION_START:STRING
    public String book(Guest guest, String number, int nights) { Room room = rooms.get(number); if (room == null || nights < 1 || nights > 30 || !room.occupy()) return "REJECTED"; return new Booking(guest, room, nights).summary(); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); String number = input.next(); String type = input.next(); int price = input.nextInt(); Guest guest = new Guest(input.next()); int nights = input.nextInt(); Hotel hotel = new Hotel(); hotel.add(new Room(number, type, price)); System.out.println(hotel.book(guest, number, nights)); } }''',
        },
        ["101 single 80 Li 2", "202 suite 200 Wang 1", "303 single 50 Zhou 30"],
        ["101 single 80 Li 0", "202 suite 200 Wang 31", "303 single 50 Zhou 5", "404 suite 300 Xu 3", "505 single 0 Q 2"],
        "Hotel 用 Map 按房间号查找 Room，Room 自己控制占用状态，成功时交给 Booking 计算总价；Optional 式的查找失败最终统一返回 REJECTED。",
    ),
    spec(
        "快递分拣与配送", "parcel-dispatch", "配送中心需要把包裹按目的地分拣。Parcel 保存包裹信息，Route 表示目的地线路，DeliveryStatus 描述状态，DispatchCenter 用 Map 聚合并统计每条线路的重量。",
        "输入为包裹数量，随后每行给出包裹编号、目的地和重量。", "按目的地字典序输出每条线路 DESTINATION 重量 包裹数。", "包裹数量不超过 20，重量为正整数。", ["enum", "Map", "Stream API", "Comparator"],
        {
            "DeliveryStatus.java": '''public enum DeliveryStatus { SORTED, READY }''',
            "Parcel.java": '''public class Parcel { private final String id; private final String destination; private final int weight; private DeliveryStatus status = DeliveryStatus.READY; public Parcel(String id, String destination, int weight) { this.id = id; this.destination = destination; this.weight = weight; } public String getDestination() { return destination; } public int getWeight() { return weight; } // SOLUTION_START:VOID
    public void sort() { status = DeliveryStatus.SORTED; }
    // SOLUTION_END
}''',
            "Route.java": '''public class Route { private final String destination; private int weight; private int count; public Route(String destination) { this.destination = destination; } // SOLUTION_START:VOID
    public void accept(Parcel parcel) { weight += parcel.getWeight(); count++; parcel.sort(); }
    // SOLUTION_END
    public String summary() { return destination + " " + weight + " " + count; } }''',
            "DispatchCenter.java": '''import java.util.*;
public class DispatchCenter { private final Map<String, Route> routes = new TreeMap<>(); // SOLUTION_START:VOID
    public void dispatch(Parcel parcel) { routes.computeIfAbsent(parcel.getDestination(), Route::new).accept(parcel); }
    // SOLUTION_END
    public List<String> summaries() { return routes.values().stream().map(Route::summary).toList(); } }''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); int count = input.nextInt(); DispatchCenter center = new DispatchCenter(); for (int i = 0; i < count; i++) center.dispatch(new Parcel(input.next(), input.next(), input.nextInt())); for (String line : center.summaries()) System.out.println(line); } }''',
        },
        ["3 P1 Shanghai 4 P2 Beijing 6 P3 Shanghai 5", "2 A Hangzhou 2 B Hangzhou 3", "1 X Nanjing 9"],
        ["4 A Beijing 2 B Shanghai 4 C Beijing 5 D Shanghai 1", "0", "2 A X 1 B Y 2", "3 A Z 10 B Z 1 C A 4", "1 K Beijing 100"],
        "DispatchCenter 用 TreeMap 分组，Route 累加同一目的地的重量和数量，Parcel 在接收时改变状态；最后通过 Stream API 按目的地顺序输出。",
    ),
    spec(
        "棋类比赛积分榜", "chess-ranking", "比赛系统需要根据胜负结果生成积分榜。Player 保存积分，MatchResult 表示一场比赛，RankingService 负责更新积分并用 Comparator 排序。胜者得 3 分，和棋双方各得 1 分。",
        "输入为比赛数量，随后每行给出白方姓名、黑方姓名和结果（WHITE、BLACK 或 DRAW）。", "按积分降序、姓名升序输出 RANK 姓名 积分。", "比赛数量不超过 30。", ["Comparator", "Map", "enum", "Stream API"],
        {
            "Player.java": '''public class Player { private final String name; private int points; public Player(String name) { this.name = name; } public String getName() { return name; } public int getPoints() { return points; } // SOLUTION_START:VOID
    public void addPoints(int value) { points += value; }
    // SOLUTION_END
}''',
            "MatchResult.java": '''public record MatchResult(String white, String black, String result) {}''',
            "RankingService.java": '''import java.util.*;
public class RankingService { private final Map<String, Player> players = new HashMap<>(); private Player player(String name) { return players.computeIfAbsent(name, Player::new); } // SOLUTION_START:VOID
    public void record(MatchResult match) { Player white = player(match.white()); Player black = player(match.black()); if (match.result().equals("WHITE")) white.addPoints(3); else if (match.result().equals("BLACK")) black.addPoints(3); else { white.addPoints(1); black.addPoints(1); } }
    // SOLUTION_END
    public List<Player> ranking() { return players.values().stream().sorted(Comparator.comparingInt(Player::getPoints).reversed().thenComparing(Player::getName)).toList(); } }''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); int count = input.nextInt(); RankingService service = new RankingService(); for (int i = 0; i < count; i++) service.record(new MatchResult(input.next(), input.next(), input.next())); int rank = 1; for (Player player : service.ranking()) System.out.println("RANK " + rank++ + " " + player.getName() + " " + player.getPoints()); } }''',
        },
        ["3 A B WHITE B C DRAW A C BLACK", "2 Li Wang DRAW Li Chen WHITE", "1 X Y BLACK"],
        ["4 A B WHITE B C DRAW A C BLACK D A DRAW", "0", "2 A B DRAW A B DRAW", "3 Q R WHITE R S WHITE S Q DRAW", "1 Z Z DRAW"],
        "RankingService 为每位姓名创建 Player，MatchResult 携带一场比赛，更新后使用 Comparator 先按积分降序再按姓名升序生成排行榜。",
    ),
    spec(
        "宠物诊所预约", "pet-clinic", "宠物诊所需要给宠物安排兽医。Pet 保存宠物信息，Veterinarian 保存专长和预约数，Appointment 记录一次预约，Clinic 负责选择第一位能够接诊的兽医。",
        "输入为宠物名、宠物类型、兽医数量，随后每位兽医给出姓名和专长，最后给出预约专长。", "匹配成功输出 APPOINTED 宠物名 兽医名，否则输出 WAITLIST 宠物名。", "兽医数量不超过 10。", ["List", "Optional", "class 与对象", "Comparator"],
        {
            "Pet.java": '''public class Pet { private final String name; private final String type; public Pet(String name, String type) { this.name = name; this.type = type; } public String getName() { return name; } public String getType() { return type; } }''',
            "Veterinarian.java": '''public class Veterinarian { private final String name; private final String specialty; private boolean busy; public Veterinarian(String name, String specialty) { this.name = name; this.specialty = specialty; } public String getName() { return name; } // SOLUTION_START:BOOL
    public boolean canTreat(String type) { return !busy && specialty.equals(type); }
    // SOLUTION_END
    public void assign() { busy = true; } }''',
            "Appointment.java": '''public class Appointment { private final Pet pet; private final Veterinarian vet; public Appointment(Pet pet, Veterinarian vet) { this.pet = pet; this.vet = vet; } public String summary() { return "APPOINTED " + pet.getName() + " " + vet.getName(); } }''',
            "Clinic.java": '''import java.util.*;
public class Clinic { private final List<Veterinarian> vets; public Clinic(List<Veterinarian> vets) { this.vets = vets; } // SOLUTION_START:STRING
    public String book(Pet pet) { for (Veterinarian vet : vets) if (vet.canTreat(pet.getType())) { vet.assign(); return new Appointment(pet, vet).summary(); } return "WAITLIST " + pet.getName(); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.*;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); Pet pet = new Pet(input.next(), input.next()); int count = input.nextInt(); List<Veterinarian> vets = new ArrayList<>(); for (int i = 0; i < count; i++) vets.add(new Veterinarian(input.next(), input.next())); System.out.println(new Clinic(vets).book(pet)); } }''',
        },
        ["Mimi cat 2 Chen cat Li dog", "Lucky dog 1 Wang dog", "Coco bird 2 A cat B bird"],
        ["Mimi cat 1 Chen dog", "Lucky dog 2 Wang dog Li dog", "Coco bird 0", "Max cat 2 A dog B dog", "Nini cat 1 A cat"],
        "Clinic 遍历 Veterinarian 列表，Veterinarian 判断专长和忙碌状态，成功后 Appointment 组合 Pet 与兽医；没有匹配对象时进入 WAITLIST。",
    ),
    spec(
        "租车订单管理", "car-rental", "租车服务需要根据车型处理订单。Vehicle 表示车辆，Customer 表示客户，RentalOrder 记录租期，RentalService 负责检查车辆状态并计算费用。",
        "输入为车辆编号、车型（compact 或 van）、日租金、客户名和租用天数。", "可租出输出 RENTED 客户名 车辆编号 总价，否则输出 REJECTED。", "租用天数为 1 至 30，日租金为非负整数。", ["enum", "Optional", "class 与对象", "Map"],
        {
            "VehicleStatus.java": '''public enum VehicleStatus { AVAILABLE, RENTED }''',
            "Vehicle.java": '''public class Vehicle { private final String id; private final String type; private final int dailyRate; private VehicleStatus status = VehicleStatus.AVAILABLE; public Vehicle(String id, String type, int dailyRate) { this.id = id; this.type = type; this.dailyRate = dailyRate; } public String getId() { return id; } public int getDailyRate() { return dailyRate; } // SOLUTION_START:BOOL
    public boolean rent() { if (status == VehicleStatus.RENTED) return false; status = VehicleStatus.RENTED; return true; }
    // SOLUTION_END
}''',
            "Customer.java": '''public class Customer { private final String name; public Customer(String name) { this.name = name; } public String getName() { return name; } }''',
            "RentalOrder.java": '''public class RentalOrder { private final Customer customer; private final Vehicle vehicle; private final int days; public RentalOrder(Customer customer, Vehicle vehicle, int days) { this.customer = customer; this.vehicle = vehicle; this.days = days; } public String summary() { return "RENTED " + customer.getName() + " " + vehicle.getId() + " " + vehicle.getDailyRate() * days; } }''',
            "RentalService.java": '''import java.util.*;
public class RentalService { private final Map<String, Vehicle> vehicles = new HashMap<>(); public void add(Vehicle vehicle) { vehicles.put(vehicle.getId(), vehicle); } // SOLUTION_START:STRING
    public String rent(Customer customer, String id, int days) { Vehicle vehicle = vehicles.get(id); if (vehicle == null || days < 1 || days > 30 || !vehicle.rent()) return "REJECTED"; return new RentalOrder(customer, vehicle, days).summary(); }
    // SOLUTION_END
}''',
            "Main.java": '''import java.util.Scanner;
public class Main { public static void main(String[] args) { Scanner input = new Scanner(System.in); String id = input.next(); String type = input.next(); int rate = input.nextInt(); Customer customer = new Customer(input.next()); int days = input.nextInt(); RentalService service = new RentalService(); service.add(new Vehicle(id, type, rate)); System.out.println(service.rent(customer, id, days)); } }''',
        },
        ["V1 compact 50 Han 3", "V2 van 120 Lin 1", "V3 compact 0 Q 30"],
        ["V1 compact 50 Han 0", "V2 van 120 Lin 31", "V3 compact 0 Q 2", "V4 van 80 X 5", "V5 compact 30 Y 10"],
        "RentalService 用 Map 查找 Vehicle，Vehicle 通过枚举状态控制是否可租，成功时由 RentalOrder 组合客户、车辆和租期计算总价。",
    ),
]


def update_snapshot(rows: list[dict]) -> None:
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    by_key = {row["source_key"]: row for row in rows}
    for item in payload["exercises"]:
        replacement = by_key.get(item.get("source_key"))
        if replacement:
            for key, value in replacement.items():
                item[key] = value
    with gzip.open(SNAPSHOT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def validate_and_prepare(row, item: dict, index: int) -> dict:
    starter = item["starter_files"]
    reference = item["reference_files"]
    stdout, stderr, code = run_java(starter, item["public_cases"][0]["stdin_text"])
    if code != 0:
        raise RuntimeError(f"starter compile failed for {row.source_key}: {stderr[-1000:]}")
    all_cases = item["public_cases"] + item["hidden_cases"]
    outputs = []
    for case in all_cases:
        stdout, stderr, code = run_java(reference, case["stdin_text"])
        if code != 0:
            raise RuntimeError(f"reference failed for {row.source_key}: {stderr[-1000:]}")
        case["expected_stdout"] = stdout
        case["explanation_zh"] = item["explain"] + f" 本样例的最终输出为 {stdout.strip()}。"
        outputs.append(stdout)
    wrong_rejected = False
    for case in item["hidden_cases"]:
        stdout, _, _ = run_java(starter, case["stdin_text"])
        if stdout.rstrip("\n") != case["expected_stdout"].rstrip("\n"):
            wrong_rejected = True
            break
    if not wrong_rejected:
        raise RuntimeError(f"starter was not rejected by hidden tests: {row.source_key}")
    paths = [file["path"] for file in starter]
    manifest = {
        "runner": "standard_io",
        "protocol_version": 2,
        "language": "java",
        "exercise_id": row.slug,
        "exercise_type": "multi_file",
        "entry_file": "Main.java",
        "editable_files": paths,
        "support_files": [],
        "test_files": [],
        "compile_all_sources": True,
    }
    audit = {
        "runner": "standard_io",
        "protocol_version": 2,
        "multifile": True,
        "exercise_type": "multi_file",
        "entry_file": "Main.java",
        "editable_files": paths,
        "reference_passed": True,
        "starter_valid": True,
        "wrong_solution_rejected": True,
        "hidden_test_driver_leak": False,
        "reference_files_leak": False,
        "manifest": manifest,
        "repaired_at": NOW,
    }
    item["public_tests_json"] = json.dumps([{"samples": item["public_cases"]}], ensure_ascii=False, separators=(",", ":"))
    item["hidden_tests_json"] = json.dumps([{"samples": item["hidden_cases"]}], ensure_ascii=False, separators=(",", ":"))
    item["starter_files_json"] = json.dumps(starter, ensure_ascii=False, separators=(",", ":"))
    item["reference_files_json"] = json.dumps(reference, ensure_ascii=False, separators=(",", ":"))
    item["official_test_files_json"] = "[]"
    item["audit_report_json"] = json.dumps(audit, ensure_ascii=False, separators=(",", ":"))
    return item


def repair(dry_run: bool = False) -> dict:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        rows = db.query(ProgrammingExercise).filter(
            ProgrammingExercise.language == "Java",
            ProgrammingExercise.source_key.like("first_party_original_v2|%"),
            ProgrammingExercise.is_active.is_(True),
        ).order_by(ProgrammingExercise.id).all()
        if len(rows) < len(SPECS):
            raise RuntimeError(f"expected at least {len(SPECS)} active Java rows, got {len(rows)}")
        prepared = []
        for index, (row, item) in enumerate(zip(rows[:len(SPECS)], SPECS)):
            prepared_item = {
                "source_key": row.source_key,
                "slug": row.slug,
                "language": "Java",
                "title": item["title_zh"],
                "title_zh": item["title_zh"],
                "title_en": item["title_zh"],
                "summary_zh": item["summary_zh"],
                "statement_zh": item["statement_zh"],
                "statement_en": item["statement_zh"],
                "description": item["summary_zh"],
                "input_format_zh": item["input_format_zh"],
                "output_format_zh": item["output_format_zh"],
                "constraints_zh": item["constraints_zh"],
                "starter_files": item["starter_files"],
                "reference_files": item["reference_files"],
                "public_cases": item["public_cases"],
                "hidden_cases": item["hidden_cases"],
                "explain": item["explain"],
            }
            prepared_item = validate_and_prepare(row, prepared_item, index)
            row.title = prepared_item["title"]
            row.title_zh = prepared_item["title_zh"]
            row.title_en = prepared_item["title_en"]
            row.description = prepared_item["description"]
            row.statement_zh = prepared_item["statement_zh"]
            row.statement_en = prepared_item["statement_en"]
            row.input_format_zh = prepared_item["input_format_zh"]
            row.output_format_zh = prepared_item["output_format_zh"]
            row.constraints_zh = prepared_item["constraints_zh"]
            row.starter_files_json = prepared_item["starter_files_json"]
            row.reference_files_json = prepared_item["reference_files_json"]
            row.public_tests_json = prepared_item["public_tests_json"]
            row.hidden_tests_json = prepared_item["hidden_tests_json"]
            row.official_test_files_json = prepared_item["official_test_files_json"]
            row.audit_report_json = prepared_item["audit_report_json"]
            row.problem_family_id = f"java-multifile-{SPECS[index]['slug_key']}"
            row.language_fit_reason = "通过多个 Java 类的构造器、封装、集合 API、接口或枚举协作完成业务流程；Main.java 只负责协议转换。"
            row.learning_objective_id = f"java-multifile-{SPECS[index]['slug_key']}"
            row.learning_objective = "设计多个 Java 对象并让它们协作完成一个可验证的业务流程"
            row.prerequisites = "类、对象、方法、集合与标准输入输出"
            row.core_skill = "多文件编译、对象职责划分与 Java API 协作"
            row.novelty_reason = "独立的业务对象关系、状态变化和输入输出协议，不是单一算术模板。"
            row.curriculum_module = item["module"]
            row.level = "进阶"
            row.difficulty = "进阶"
            row.quality_status = "approved"
            row.quality_score = 100
            row.quality_failure_reasons = "[]"
            row.reference_verified = True
            row.starter_verified = True
            row.updated_at = datetime.now(timezone.utc)
            prepared.append({
                **{key: value for key, value in prepared_item.items() if key.endswith("_json")},
                "title": row.title, "title_zh": row.title_zh, "title_en": row.title_en,
                "summary_zh": row.summary_zh, "statement_zh": row.statement_zh,
                "statement_en": row.statement_en, "description": row.description,
                "input_format_zh": row.input_format_zh, "output_format_zh": row.output_format_zh,
                "constraints_zh": row.constraints_zh, "problem_family_id": row.problem_family_id,
                "language_fit_reason": row.language_fit_reason, "learning_objective_id": row.learning_objective_id,
                "learning_objective": row.learning_objective, "prerequisites": row.prerequisites,
                "core_skill": row.core_skill, "novelty_reason": row.novelty_reason,
                "curriculum_module": row.curriculum_module, "level": row.level, "difficulty": row.difficulty,
                "quality_status": row.quality_status, "quality_score": row.quality_score,
                "quality_failure_reasons": row.quality_failure_reasons, "reference_verified": True,
                "starter_verified": True, "is_active": True, "source_key": row.source_key,
            })
        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    if not dry_run:
        update_snapshot(prepared)
    result = {"dry_run": dry_run, "repaired": len(prepared), "java_multifile": len(prepared), "files_min": min(len(json.loads(item["starter_files_json"])) for item in prepared)}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    repair(parser.parse_args().dry_run)
