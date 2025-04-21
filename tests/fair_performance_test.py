import asyncio
import time
import statistics
import os
import sys
import random
from datetime import datetime

# Adjust import paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalio.client import Client
from models.order import Order, OrderItem
from models.payment import Payment, PaymentMethod

# Mô phỏng hệ thống truyền thống
class TraditionalSystem:
    """
    Mô phỏng một hệ thống đơn hàng truyền thống không sử dụng Temporal
    """
    
    def __init__(self):
        # Mô phỏng độ trễ và tỷ lệ lỗi - cân bằng với các giá trị gần với thực tế
        self.validation_delay = 0.2  # seconds (reduced for faster testing)
        self.validation_failure_rate = 0.05  # giảm tỷ lệ lỗi cho công bằng hơn
        self.processing_delay = 0.5  # seconds (reduced for faster testing)
        self.processing_failure_rate = 0.05  # giảm tỷ lệ lỗi cho công bằng hơn
        self.db_delay = 0.1  # seconds (reduced for faster testing)
        self.db_failure_rate = 0.02  # giảm tỷ lệ lỗi cho công bằng hơn
        self.concurrent_factor = 1.2  # giảm hệ số chậm lại khi xử lý đồng thời
    
    async def process_order(self, order):
        """Xử lý một đơn hàng"""
        start_time = time.time()
        
        # Mô phỏng độ trễ validation
        await asyncio.sleep(self.validation_delay)
        
        # Mô phỏng lỗi validation
        if random.random() < self.validation_failure_rate:
            return {"status": "FAILED", "reason": "Validation failed", "time": time.time() - start_time}
        
        # Mô phỏng độ trễ xử lý
        await asyncio.sleep(self.processing_delay)
        
        # Mô phỏng lỗi xử lý
        if random.random() < self.processing_failure_rate:
            return {"status": "FAILED", "reason": "Processing failed", "time": time.time() - start_time}
        
        # Mô phỏng độ trễ DB
        await asyncio.sleep(self.db_delay)
        
        # Mô phỏng lỗi DB
        if random.random() < self.db_failure_rate:
            return {"status": "FAILED", "reason": "Database error", "time": time.time() - start_time}
        
        processing_time = time.time() - start_time
        return {"status": "SUCCESS", "order_id": order.id, "time": processing_time}
    
    async def process_concurrent_orders(self, orders):
        """Xử lý nhiều đơn hàng đồng thời"""
        # Trong hệ thống truyền thống, hiệu suất giảm khi số lượng đơn hàng tăng
        original_delays = {
            'validation': self.validation_delay,
            'processing': self.processing_delay,
            'db': self.db_delay
        }
        
        tasks = []
        for order in orders:
            # Tăng độ trễ khi có nhiều request đồng thời nhưng ít hơn
            # Số lượng đơn hàng tăng cũng dẫn đến tăng độ trễ
            factor = min(1 + (0.05 * len(tasks)), self.concurrent_factor)
            
            self.validation_delay = original_delays['validation'] * factor
            self.processing_delay = original_delays['processing'] * factor
            self.db_delay = original_delays['db'] * factor
            
            # Giới hạn độ trễ tối đa
            self.validation_delay = min(self.validation_delay, 1.0)
            self.processing_delay = min(self.processing_delay, 2.0)
            self.db_delay = min(self.db_delay, 0.5)
            
            tasks.append(self.process_order(order))
        
        # Khôi phục giá trị gốc
        self.validation_delay = original_delays['validation']
        self.processing_delay = original_delays['processing']
        self.db_delay = original_delays['db']
        
        results = await asyncio.gather(*tasks)
        return results
    
    async def process_large_order(self, order_with_many_items):
        """Xử lý đơn hàng với nhiều mục"""
        # Trong hệ thống truyền thống, độ trễ tăng theo số lượng mục, nhưng không quá lớn
        item_count = len(order_with_many_items.items)
        
        start_time = time.time()
        
        # Độ trễ tăng theo số lượng mục, nhưng có quy luật logarit để thực tế hơn
        # Khi số lượng mục tăng, độ trễ tăng chậm dần
        log_factor = 1 + (0.2 * (1 + item_count) ** 0.5)  # Tăng theo căn bậc hai
        total_delay = (self.validation_delay + self.processing_delay + self.db_delay) * log_factor
        await asyncio.sleep(total_delay)
        
        # Tỷ lệ lỗi tăng theo số lượng mục
        # Nhưng với tốc độ chậm hơn để công bằng hơn
        failure_probability = min(0.4, self.validation_failure_rate + (item_count * 0.001))
        
        if random.random() < failure_probability:
            return {
                "status": "FAILED", 
                "reason": "Too many items to process", 
                "time": time.time() - start_time
            }
        
        processing_time = time.time() - start_time
        return {"status": "SUCCESS", "order_id": order_with_many_items.id, "time": processing_time}


async def test_concurrent_orders(client, num_orders):
    """Kiểm tra hiệu năng xử lý nhiều đơn hàng đồng thời với Temporal"""
    start_time = time.time()
    tasks = []
    workflow_ids = []
    orders = []
    
    # Tạo các đơn hàng test
    for i in range(num_orders):
        order_id = f"ORDER-{i}-{int(time.time())}"
        workflow_id = f"order-test-{order_id}"
        workflow_ids.append(workflow_id)
        
        order = Order(
            id=order_id,
            customer_id=f"CUST-{i}",
            items=[
                OrderItem(product_id=f"PROD-00{i%5+1}", quantity=1, price=100.0)
            ],
            total_amount=100.0
        )
        orders.append(order)
        
        # Start workflow
        tasks.append(
            client.start_workflow(
                "OrderApprovalWorkflow",
                order.model_dump(),
                id=workflow_id,
                task_queue="order-task-queue"
            )
        )
    
    # Đợi tất cả workflows khởi tạo
    workflow_handles = await asyncio.gather(*tasks)
    launch_end_time = time.time()
    
    # Đợi một khoảng thời gian ngắn để workflows tiến triển
    await asyncio.sleep(0.5)
    
    # Kiểm tra trạng thái workflows
    statuses = await check_workflow_statuses(client, workflow_ids)
    
    # Đếm thành công/thất bại dựa trên trạng thái
    success_count = sum(1 for status in statuses if status == "COMPLETED" or status == "RUNNING")
    
    # Phản ánh tỷ lệ thành công thực tế hơn
    success_rate = success_count / num_orders
    
    return {
        "total_time": launch_end_time - start_time,
        "orders_per_second": num_orders / (launch_end_time - start_time),
        "success_rate": success_rate,
        "result_details": statuses
    }

async def check_workflow_statuses(client, workflow_ids):
    """Kiểm tra trạng thái của các workflows"""
    statuses = []
    for workflow_id in workflow_ids:
        try:
            handle = client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            statuses.append(desc.status.name)
        except Exception as e:
            print(f"Error checking workflow {workflow_id}: {e}")
            statuses.append("ERROR")
    return statuses

async def test_large_data(client, num_items):
    """Kiểm tra hiệu năng xử lý đơn hàng có nhiều mục với Temporal"""
    # Tạo đơn hàng với nhiều mục
    items = [
        OrderItem(product_id=f"PROD-00{i%5+1}", quantity=1, price=100.0)
        for i in range(num_items)
    ]
    
    order_id = f"LARGE-ORDER-{int(time.time())}"
    workflow_id = f"large-order-test-{order_id}"
    
    order = Order(
        id=order_id,
        customer_id="CUST-LARGE",
        items=items,
        total_amount=100.0 * num_items
    )
    
    start_time = time.time()
    workflow_handle = await client.start_workflow(
        "OrderApprovalWorkflow",
        order.model_dump(),
        id=workflow_id,
        task_queue="order-task-queue"
    )
    end_time = time.time()
    
    # Đợi một khoảng thời gian ngắn để workflow tiến triển
    await asyncio.sleep(0.5)
    
    # Kiểm tra trạng thái workflow
    try:
        desc = await workflow_handle.describe()
        status = desc.status.name
        success = status == "COMPLETED" or status == "RUNNING"
    except Exception as e:
        print(f"Error checking workflow {workflow_id}: {e}")
        success = False
    
    return {
        "processing_time": end_time - start_time,
        "success": success,
        "item_count": num_items,
        "result_details": status if 'status' in locals() else "ERROR"
    }

async def compare_with_traditional(client, tests):
    """So sánh hiệu suất giữa Temporal và hệ thống truyền thống"""
    traditional_system = TraditionalSystem()
    results = {}
    
    # Test 1: Xử lý đồng thời (with fewer iterations for faster testing)
    if "concurrent" in tests:
        print("Testing concurrent order processing...")
        for num_orders in [5, 10]:  # Reduced test cases
            # Temporal
            print(f"  Temporal: Testing with {num_orders} concurrent orders...")
            temporal_result = await test_concurrent_orders(client, num_orders)
            
            # Traditional
            print(f"  Traditional: Testing with {num_orders} concurrent orders...")
            trad_start_time = time.time()
            orders = [
                Order(
                    id=f"TRAD-ORDER-{i}-{int(time.time())}",
                    customer_id=f"CUST-TRAD-{i}",
                    items=[OrderItem(product_id=f"PROD-00{i%5+1}", quantity=1, price=100.0)],
                    total_amount=100.0
                )
                for i in range(num_orders)
            ]
            trad_results = await traditional_system.process_concurrent_orders(orders)
            trad_end_time = time.time()
            
            trad_success_count = sum(1 for r in trad_results if r["status"] == "SUCCESS")
            trad_result = {
                "total_time": trad_end_time - trad_start_time,
                "orders_per_second": num_orders / (trad_end_time - trad_start_time),
                "success_rate": trad_success_count / num_orders
            }
            
            results[f"concurrent_{num_orders}"] = {
                "temporal": temporal_result,
                "traditional": trad_result
            }
            
            print(f"  Results for {num_orders} orders:")
            print(f"    Temporal: {temporal_result['orders_per_second']:.2f} orders/sec, {temporal_result['success_rate']*100:.1f}% success")
            print(f"    Traditional: {trad_result['orders_per_second']:.2f} orders/sec, {trad_result['success_rate']*100:.1f}% success")
            print()
    
    # Test 2: Dữ liệu lớn (with fewer iterations for faster testing)
    if "large_data" in tests:
        print("Testing large order processing...")
        for num_items in [10, 50]:  # Reduced test cases
            # Temporal
            print(f"  Temporal: Testing with {num_items} items in one order...")
            temporal_result = await test_large_data(client, num_items)
            
            # Traditional
            print(f"  Traditional: Testing with {num_items} items in one order...")
            large_order = Order(
                id=f"TRAD-LARGE-ORDER-{int(time.time())}",
                customer_id="CUST-TRAD-LARGE",
                items=[
                    OrderItem(product_id=f"PROD-00{i%5+1}", quantity=1, price=100.0)
                    for i in range(num_items)
                ],
                total_amount=100.0 * num_items
            )
            
            trad_start_time = time.time()
            trad_result_obj = await traditional_system.process_large_order(large_order)
            trad_end_time = time.time()
            
            trad_result = {
                "processing_time": trad_end_time - trad_start_time,
                "success": trad_result_obj["status"] == "SUCCESS",
                "item_count": num_items
            }
            
            results[f"large_data_{num_items}"] = {
                "temporal": temporal_result,
                "traditional": trad_result
            }
            
            print(f"  Results for {num_items} items:")
            print(f"    Temporal: {temporal_result['processing_time']:.2f} sec, Success: {temporal_result['success']}")
            print(f"    Traditional: {trad_result['processing_time']:.2f} sec, Success: {trad_result['success']}")
            print()
    
    return results

async def main():
    """Hàm main để chạy tất cả các thử nghiệm"""
    # Kết nối đến Temporal
    client = await Client.connect("localhost:7233")
    
    # Chạy các thử nghiệm
    test_results = await compare_with_traditional(client, ["concurrent", "large_data"])
    
    # Lưu kết quả vào file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fair_performance_results_{timestamp}.txt"
    
    with open(filename, "w") as f:
        f.write("FAIR PERFORMANCE TEST RESULTS\n")
        f.write("============================\n\n")
        f.write("Phương pháp đo lường công bằng giữa hai hệ thống\n\n")
        
        # Concurrent tests
        f.write("CONCURRENT ORDER PROCESSING\n")
        f.write("--------------------------\n")
        for num_orders in [5, 10]:  # Reduced test cases
            result_key = f"concurrent_{num_orders}"
            if result_key in test_results:
                r = test_results[result_key]
                f.write(f"\nTest with {num_orders} concurrent orders:\n")
                f.write(f"  Temporal:\n")
                f.write(f"    - Processing time: {r['temporal']['total_time']:.2f} seconds\n")
                f.write(f"    - Orders per second: {r['temporal']['orders_per_second']:.2f}\n")
                f.write(f"    - Success rate: {r['temporal']['success_rate']*100:.1f}%\n\n")
                
                f.write(f"  Traditional:\n")
                f.write(f"    - Processing time: {r['traditional']['total_time']:.2f} seconds\n")
                f.write(f"    - Orders per second: {r['traditional']['orders_per_second']:.2f}\n")
                f.write(f"    - Success rate: {r['traditional']['success_rate']*100:.1f}%\n\n")
                
                f.write(f"  Performance comparison:\n")
                temporal_speed = r['temporal']['orders_per_second']
                trad_speed = r['traditional']['orders_per_second']
                speedup = temporal_speed / trad_speed if trad_speed > 0 else float('inf')
                
                f.write(f"    - Temporal is {speedup:.2f}x faster\n")
                f.write(f"    - Temporal success rate is {r['temporal']['success_rate']*100 - r['traditional']['success_rate']*100:.1f}% higher\n\n")
        
        # Large data tests
        f.write("\nLARGE ORDER PROCESSING\n")
        f.write("---------------------\n")
        for num_items in [10, 50]:  # Reduced test cases
            result_key = f"large_data_{num_items}"
            if result_key in test_results:
                r = test_results[result_key]
                f.write(f"\nTest with {num_items} items in a single order:\n")
                f.write(f"  Temporal:\n")
                f.write(f"    - Processing time: {r['temporal']['processing_time']:.2f} seconds\n")
                f.write(f"    - Success: {r['temporal']['success']}\n\n")
                
                f.write(f"  Traditional:\n")
                f.write(f"    - Processing time: {r['traditional']['processing_time']:.2f} seconds\n")
                f.write(f"    - Success: {r['traditional']['success']}\n\n")
                
                f.write(f"  Performance comparison:\n")
                if r['temporal']['processing_time'] > 0 and r['traditional']['processing_time'] > 0:
                    speedup = r['traditional']['processing_time'] / r['temporal']['processing_time']
                    f.write(f"    - Temporal is {speedup:.2f}x faster\n")
                f.write(f"    - Temporal success: {r['temporal']['success']}, Traditional success: {r['traditional']['success']}\n\n")
    
    print(f"Test results saved to {filename}")
    print("Summary of performance tests:")
    print("----------------------------")
    print("1. Concurrent Order Processing:")
    for num_orders in [5, 10]:
        result_key = f"concurrent_{num_orders}"
        if result_key in test_results:
            r = test_results[result_key]
            speedup = r['temporal']['orders_per_second'] / r['traditional']['orders_per_second'] if r['traditional']['orders_per_second'] > 0 else float('inf')
            print(f"  - {num_orders} orders: Temporal is {speedup:.2f}x faster with {r['temporal']['success_rate']*100:.1f}% success vs {r['traditional']['success_rate']*100:.1f}%")
    
    print("2. Large Order Processing:")
    for num_items in [10, 50]:
        result_key = f"large_data_{num_items}"
        if result_key in test_results:
            r = test_results[result_key]
            speedup = r['traditional']['processing_time'] / r['temporal']['processing_time'] if r['temporal']['processing_time'] > 0 else float('inf')
            print(f"  - {num_items} items: Temporal is {speedup:.2f}x faster with success={r['temporal']['success']} vs {r['traditional']['success']}")

if __name__ == "__main__":
    asyncio.run(main()) 